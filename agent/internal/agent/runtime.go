package agent

import (
	"context"
	"errors"
	"net/netip"
	"path/filepath"
	"time"
)

func Run(ctx context.Context, configPath string, noTUN bool, port uint16, publicEndpoint string) (runError error) {
	var i Identity
	stage := "options"
	startupComplete := false
	defer func() {
		if runError != nil && !startupComplete {
			recordStartupFailure(configPath, i, stage, runError, noTUN, port)
			code := "startup_failed"
			var failure *startupFailure
			if errors.As(runError, &failure) {
				code = failure.Code
			}
			recordStartupEvent(stage, code)
		}
	}()
	var advertised *Candidate
	if publicEndpoint != "" {
		endpoint, err := netip.ParseAddrPort(publicEndpoint)
		if err != nil || endpoint.Port() == 0 {
			return errors.New("invalid advertised public endpoint")
		}
		ip, allowed := normalizeDirectAddress(endpoint.Addr(), netip.Prefix{}, false)
		if !allowed || ip.IsPrivate() {
			return errors.New("advertised endpoint must be a public IPv4 address")
		}
		advertised = &Candidate{IP: ip.String(), Port: endpoint.Port(), Source: "advertised"}
	}
	stage = "identity"
	var e error
	i, e = LoadIdentity(configPath)
	if e != nil {
		return failStartup("identity_load_failed", e)
	}
	stage = "control"
	control, e := NewControl(i.ControlURL, i.DeviceToken)
	if e != nil {
		return failStartup("control_config_failed", e)
	}
	n, e := control.Config(ctx, i)
	if e != nil {
		return failStartup("control_config_failed", e)
	}
	lastConfig := time.Now()
	id, _ := ParseID(i.PeerID)
	bind := NewBind(id)
	bind.ReplacePeers(n)
	var engine *Engine
	if !noTUN {
		stage = "interface"
		engine, e = NewEngine(i, bind, n, port)
		if e != nil {
			return e
		}
		// Cold Windows CIM setup can outlast the authorization TTL. Refresh
		// peer keys before applying WireGuard after the slow interface stage.
		if time.Since(lastConfig) >= 15*time.Second {
			stage = "control_refresh"
			fresh, err := control.Config(ctx, i)
			if err != nil {
				engine.Close()
				return failStartup("control_config_failed", err)
			}
			n = fresh
			bind.ReplacePeers(fresh)
			lastConfig = time.Now()
		}
		stage = "wireguard"
		if e = engine.Apply(n); e != nil {
			engine.Close()
			return failStartup("wireguard_config_failed", e)
		}
		if e = engine.Up(); e != nil {
			engine.Close()
			return failStartup("wireguard_start_failed", e)
		}
		defer engine.Close()
	} else {
		stage = "udp"
		if _, _, e = bind.Open(port); e != nil {
			return failStartup("udp_bind_failed", e)
		}
		defer bind.Close()
	}
	relayCtx, relayCancel := context.WithCancel(ctx)
	defer relayCancel()
	relay := NewWSRelay(n.RelayURL, i.DeviceToken, bind)
	defer relay.Close()
	bind.SetRelay(relay)
	go relay.Run(relayCtx)
	candidates := discoverCandidates(ctx, bind, n.STUNServers, advertised)
	var lastSuccess = time.Time{}
	lastHeartbeat := time.Time{}
	lastDiscovery := time.Now()
	ticker := time.NewTicker(time.Second)
	defer ticker.Stop()
	status := func() PublicStatus {
		s := PublicStatus{SchemaVersion: 1, Provider: "rlink-fabric", DeviceID: i.PeerID, Name: i.Name, ControlURL: i.ControlURL, UpdatedAt: time.Now().Unix(), Mode: "vpn", ListenPort: bind.Port(), Peers: bind.Status()}
		for _, c := range candidates {
			s.Candidates = append(s.Candidates, PublicCandidate{IP: c.IP, Port: c.Port, Source: c.Source})
		}
		if noTUN {
			s.Mode = "transport-test"
		}
		s.Control.Connected = !lastSuccess.IsZero() && time.Since(lastSuccess) < time.Duration(n.TTLSeconds)*time.Second
		s.Control.LastSuccessAt = lastSuccess.Unix()
		if lastSuccess.IsZero() {
			s.Control.LastSuccessAt = 0
		}
		s.TUN.Ready = engine != nil
		s.TUN.IP = i.VirtualIP
		if engine != nil {
			s.TUN.Name = engine.name
			engine.FillStatus(s.Peers)
		}
		now := time.Now().Unix()
		for k, p := range s.Peers {
			if p.LastHandshake > 0 {
				age := now - p.LastHandshake
				s.Peers[k].HandshakeAgeSeconds = &age
			}
		}
		return s
	}
	dir := filepath.Dir(configPath)
	stage = "status"
	if e = SavePublicStatus(dir, status()); e != nil {
		return failStartup("status_write_failed", e)
	}
	startupComplete = true
	defer func() {
		s := status()
		s.Control.Connected = false
		s.TUN.Ready = false
		s.StatusError = "stopped"
		for k := range s.Peers {
			s.Peers[k].Path = "offline"
		}
		_ = SavePublicStatus(dir, s)
	}()
	for {
		if time.Since(lastConfig) >= time.Duration(n.TTLSeconds)*time.Second {
			bind.Expire()
			if engine != nil {
				engine.Expire()
			}
		}
		if time.Since(lastHeartbeat) >= time.Duration(n.HeartbeatInterval)*time.Second {
			lastHeartbeat = time.Now()
			s := status()
			version, err := control.Heartbeat(ctx, candidates, s.TUN.Ready, s.Peers, n.ConfigVersion)
			if err == nil {
				lastSuccess = time.Now()
			}
			// Refresh all peer authorization at every heartbeat. Heartbeat does
			// not extend the cached pair secret's TTL on its own.
			if err == nil || time.Since(lastConfig) >= 15*time.Second || version != n.ConfigVersion {
				fresh, err := control.Config(ctx, i)
				if err == nil {
					bind.ReplacePeers(fresh)
					if engine != nil {
						if err = engine.Apply(fresh); err != nil {
							bind.Expire()
							engine.Expire()
						}
					}
					if err == nil {
						lastConfig = time.Now()
						n = fresh
						lastSuccess = time.Now()
					}
				}
			}
		}
		if time.Since(lastDiscovery) > 30*time.Second {
			candidates = discoverCandidates(ctx, bind, n.STUNServers, advertised)
			lastDiscovery = time.Now()
		}
		if e = SavePublicStatus(dir, status()); e != nil {
			return errors.New("cannot write public agent status")
		}
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}
func discoverCandidates(ctx context.Context, b *Bind, servers []string, advertised *Candidate) []Candidate {
	b.mu.Lock()
	pool := b.ownPool
	b.mu.Unlock()
	out := LocalCandidates(b.Port(), pool)
	for _, server := range servers {
		cctx, cancel := context.WithTimeout(ctx, 2*time.Second)
		c, e := b.Discover(cctx, server)
		cancel()
		if e == nil {
			found := false
			for _, old := range out {
				if old.IP == c.IP && old.Port == c.Port {
					found = true
				}
			}
			if !found {
				if len(out) >= 16 {
					out = out[:15]
				}
				out = append(out, c)
			}
		}
	}
	if advertised != nil {
		found := false
		for _, old := range out {
			if old.IP == advertised.IP && old.Port == advertised.Port {
				found = true
			}
		}
		if !found {
			if len(out) >= 16 {
				out = out[:15]
			}
			out = append(out, *advertised)
		}
	}
	return out
}
