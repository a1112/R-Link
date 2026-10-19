package agent

import (
	"encoding/hex"
	"errors"
	"fmt"
	"strconv"
	"strings"
	"sync"

	"golang.zx2c4.com/wireguard/device"
	"golang.zx2c4.com/wireguard/tun"
)

type Engine struct {
	mu      sync.Mutex
	device  *device.Device
	bind    *Bind
	known   map[string]PeerConfig
	name    string
	cleanup func()
}

func NewEngine(i Identity, b *Bind, n NetworkConfig, port uint16) (*Engine, error) {
	t, e := tun.CreateTUN(interfaceName(), 1280)
	if e != nil {
		return nil, failStartup("tun_create_failed", e)
	}
	name, e := t.Name()
	if e != nil {
		_ = t.Close()
		return nil, failStartup("tun_name_failed", e)
	}
	cleanup, e := configureInterface(name, n.VirtualIP, n.PrefixLength)
	if e != nil {
		_ = t.Close()
		code := "route_config_failed"
		var commandError *platformCommandError
		if errors.As(e, &commandError) && commandError.TimedOut {
			code = "route_config_timeout"
		}
		return nil, failStartup(code, e)
	}
	engine, e := newEngineWithTUN(i, b, t, name, cleanup, port)
	if e != nil {
		cleanup()
		_ = t.Close()
		return nil, e
	}
	return engine, nil
}
func newEngineWithTUN(i Identity, b *Bind, t tun.Device, name string, cleanup func(), ports ...uint16) (*Engine, error) {
	private, e := decodeKey(i.PrivateKey)
	if e != nil {
		return nil, e
	}
	d := device.NewDevice(t, b, device.NewLogger(device.LogLevelSilent, ""))
	port := uint16(0)
	if len(ports) > 0 {
		port = ports[0]
	}
	if e = d.IpcSet("private_key=" + hex.EncodeToString(private[:]) + fmt.Sprintf("\nlisten_port=%d\n", port)); e != nil {
		d.Close()
		return nil, errors.New("WireGuard key configuration failed")
	}
	return &Engine{device: d, bind: b, known: map[string]PeerConfig{}, name: name, cleanup: cleanup}, nil
}
func (e *Engine) Apply(n NetworkConfig) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	var cfg strings.Builder
	next := map[string]PeerConfig{}
	for _, p := range n.Peers {
		next[p.PeerID] = p
	}
	for id, old := range e.known {
		p, ok := next[id]
		if !ok || p.PublicKey != old.PublicKey {
			k, _ := decodeKey(old.PublicKey)
			fmt.Fprintf(&cfg, "public_key=%s\nremove=true\n", hex.EncodeToString(k[:]))
		}
	}
	for _, p := range n.Peers {
		old, exists := e.known[p.PeerID]
		if exists && old.PublicKey == p.PublicKey && old.VirtualIP == p.VirtualIP {
			continue
		}
		k, err := decodeKey(p.PublicKey)
		if err != nil {
			return err
		}
		fmt.Fprintf(&cfg, "public_key=%s\nendpoint=%s\nreplace_allowed_ips=true\nallowed_ip=%s/32\npersistent_keepalive_interval=15\n", hex.EncodeToString(k[:]), p.PeerID, p.VirtualIP)
	}
	if cfg.Len() > 0 {
		if err := e.device.IpcSet(cfg.String()); err != nil {
			return errors.New("WireGuard peer configuration failed")
		}
	}
	e.known = next
	return nil
}
func (e *Engine) Up() error { return e.device.Up() }
func (e *Engine) Expire() {
	e.mu.Lock()
	defer e.mu.Unlock()
	_ = e.device.IpcSet("replace_peers=true\n")
	e.known = map[string]PeerConfig{}
}
func (e *Engine) Close() {
	e.device.Close()
	if e.cleanup != nil {
		e.cleanup()
	}
}
func (e *Engine) FillStatus(peers []PeerStatus) {
	raw, err := e.device.IpcGet()
	if err != nil {
		return
	}
	e.mu.Lock()
	byKey := map[string]string{}
	for id, p := range e.known {
		key, _ := decodeKey(p.PublicKey)
		byKey[hex.EncodeToString(key[:])] = id
	}
	e.mu.Unlock()
	indices := map[string]int{}
	for i, p := range peers {
		indices[p.PeerID] = i
	}
	index := -1
	for _, line := range strings.Split(raw, "\n") {
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			continue
		}
		if key == "public_key" {
			id := byKey[value]
			var ok bool
			index, ok = indices[id]
			if !ok {
				index = -1
			}
			continue
		}
		if index < 0 {
			continue
		}
		switch key {
		case "last_handshake_time_sec":
			v, _ := strconv.ParseInt(value, 10, 64)
			peers[index].LastHandshake = v
		case "rx_bytes":
			v, _ := strconv.ParseUint(value, 10, 64)
			peers[index].RxBytes = v
		case "tx_bytes":
			v, _ := strconv.ParseUint(value, 10, 64)
			peers[index].TxBytes = v
		}
	}
}
