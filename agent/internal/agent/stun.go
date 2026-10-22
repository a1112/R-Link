package agent

import (
	"context"
	"errors"
	"net"
	"net/netip"
	"net/url"
	"strconv"
	"strings"
	"time"

	"github.com/pion/stun/v3"
)

type stunRequest struct {
	answer  chan []byte
	address netip.AddrPort
}

func (b *Bind) handleSTUN(packet []byte, source netip.AddrPort) bool {
	if !stun.IsMessage(packet) {
		return false
	}
	m := new(stun.Message)
	m.Raw = packet
	if m.Decode() != nil {
		return true
	}
	b.mu.Lock()
	pending, ok := b.stun[m.TransactionID]
	b.mu.Unlock()
	if ok && source == pending.address {
		select {
		case pending.answer <- packet:
		default:
		}
	}
	return true
}
func (b *Bind) Discover(ctx context.Context, server string) (Candidate, error) {
	u, e := url.Parse(server)
	if e != nil || u.Scheme != "stun" {
		return Candidate{}, errors.New("invalid STUN URL")
	}
	host := u.Host
	if host == "" {
		host = u.Opaque
	}
	host = strings.TrimPrefix(host, "//")
	if _, _, e := net.SplitHostPort(host); e != nil {
		host = net.JoinHostPort(host, "3478")
	}
	hostname, portText, e := net.SplitHostPort(host)
	if e != nil {
		return Candidate{}, errors.New("invalid STUN endpoint")
	}
	port, e := strconv.ParseUint(portText, 10, 16)
	if e != nil || port == 0 {
		return Candidate{}, errors.New("invalid STUN port")
	}
	ips, e := net.DefaultResolver.LookupNetIP(ctx, "ip4", hostname)
	if e != nil || len(ips) == 0 {
		return Candidate{}, errors.New("STUN DNS resolution failed")
	}
	target := netip.AddrPortFrom(ips[0].Unmap(), uint16(port))
	msg, e := stun.Build(stun.TransactionID, stun.BindingRequest)
	if e != nil {
		return Candidate{}, e
	}
	answer := make(chan []byte, 1)
	b.mu.Lock()
	uconn := b.udp
	if uconn == nil {
		b.mu.Unlock()
		return Candidate{}, errors.New("UDP bind is not open")
	}
	b.stun[msg.TransactionID] = stunRequest{answer: answer, address: target}
	b.mu.Unlock()
	defer func() { b.mu.Lock(); delete(b.stun, msg.TransactionID); b.mu.Unlock() }()
	if _, e = uconn.WriteToUDPAddrPort(msg.Raw, target); e != nil {
		return Candidate{}, e
	}
	retry := time.NewTimer(500 * time.Millisecond)
	defer retry.Stop()
	for {
		select {
		case <-ctx.Done():
			return Candidate{}, ctx.Err()
		case <-retry.C:
			if _, e = uconn.WriteToUDPAddrPort(msg.Raw, target); e != nil {
				return Candidate{}, e
			}
			retry.Reset(time.Second)
		case raw := <-answer:
			response := &stun.Message{Raw: raw}
			if response.Decode() != nil || response.Type != stun.BindingSuccess {
				return Candidate{}, errors.New("invalid STUN response")
			}
			var mapped stun.XORMappedAddress
			if mapped.GetFrom(response) != nil {
				return Candidate{}, errors.New("STUN missing mapped address")
			}
			a, ok := netip.AddrFromSlice(mapped.IP)
			a = a.Unmap()
			if !ok || !a.Is4() || mapped.Port < 1 || mapped.Port > 65535 {
				return Candidate{}, errors.New("invalid STUN mapped address")
			}
			return Candidate{IP: a.String(), Port: uint16(mapped.Port), Source: "stun"}, nil
		}
	}
}
func LocalCandidates(port uint16, ownPool netip.Prefix) []Candidate {
	var out []Candidate
	if port == 0 {
		return out
	}
	ifs, e := net.Interfaces()
	if e != nil {
		return out
	}
	for _, iface := range ifs {
		addrs, _ := iface.Addrs()
		var addressStrings []string
		for _, a := range addrs {
			addressStrings = append(addressStrings, a.String())
		}
		for _, candidate := range interfaceCandidates(iface, addressStrings, port, ownPool) {
			out = append(out, candidate)
			if len(out) >= 16 {
				return out
			}
		}
	}
	return out
}

// ServeSTUN implements RFC 5389 binding for the project's own UDP discovery
// endpoint. It never proxies traffic and rate-limits source addresses.
func ServeSTUN(ctx context.Context, address string) error {
	a, e := net.ResolveUDPAddr("udp4", address)
	if e != nil {
		return e
	}
	u, e := net.ListenUDP("udp4", a)
	if e != nil {
		return e
	}
	return serveSTUNConn(ctx, u)
}
func serveSTUNConn(ctx context.Context, u *net.UDPConn) error {
	defer u.Close()
	go func() { <-ctx.Done(); _ = u.Close() }()
	type limit struct {
		at    time.Time
		count int
	}
	limits := map[netip.Addr]limit{}
	buf := make([]byte, 1024)
	global := limit{at: time.Now()}
	for {
		n, src, e := u.ReadFromUDPAddrPort(buf)
		if e != nil {
			if ctx.Err() != nil {
				return nil
			}
			return e
		}
		src = netip.AddrPortFrom(src.Addr().Unmap(), src.Port())
		now := time.Now()
		if now.Sub(global.at) > time.Second {
			global = limit{at: now}
		}
		global.count++
		if global.count > 1000 {
			continue
		}
		l, exists := limits[src.Addr()]
		if !exists && len(limits) >= 10000 {
			for k, v := range limits {
				if now.Sub(v.at) > time.Minute {
					delete(limits, k)
				}
			}
			if len(limits) >= 10000 {
				continue
			}
		}
		if now.Sub(l.at) > time.Second {
			l = limit{at: now}
		}
		l.count++
		limits[src.Addr()] = l
		if l.count > 20 {
			continue
		}
		if !stun.IsMessage(buf[:n]) {
			continue
		}
		m := &stun.Message{Raw: append([]byte(nil), buf[:n]...)}
		if m.Decode() != nil || m.Type != stun.BindingRequest {
			continue
		}
		response, e := stun.Build(stun.NewTransactionIDSetter(m.TransactionID), stun.BindingSuccess, &stun.XORMappedAddress{IP: net.IP(src.Addr().AsSlice()), Port: int(src.Port())})
		if e == nil {
			_, _ = u.WriteToUDPAddrPort(response.Raw, src)
		}
	}
}
