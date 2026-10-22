package agent

import (
	"context"
	"errors"
	"net"
	"net/netip"
	"sync"
	"time"

	"golang.zx2c4.com/wireguard/conn"
)

type virtualEndpoint struct {
	id ID
	ip netip.Addr
}

func (e *virtualEndpoint) ClearSrc()           {}
func (e *virtualEndpoint) SrcToString() string { return "" }
func (e *virtualEndpoint) DstToString() string { return e.id.String() }
func (e *virtualEndpoint) DstToBytes() []byte  { return e.id[:] }
func (e *virtualEndpoint) DstIP() netip.Addr   { return e.ip }
func (e *virtualEndpoint) SrcIP() netip.Addr   { return netip.Addr{} }

type pendingProbe struct {
	peer    ID
	address netip.AddrPort
	relay   bool
	at      time.Time
}
type peerState struct {
	config  PeerConfig
	id      ID
	key     [32]byte
	routes  map[string]route
	current string
	seen    nonceCache
}
type received struct {
	payload []byte
	id      ID
	ip      netip.Addr
}

// Bind gives WireGuard stable peer UUID endpoints while discovering and
// selecting authenticated UDP candidates or an opaque WSS relay underneath.
type Bind struct {
	mu         sync.Mutex
	own        ID
	peers      map[ID]*peerState
	pending    map[[8]byte]pendingProbe
	udp        *net.UDPConn
	in         chan received
	done       chan struct{}
	opened     bool
	closed     bool
	relay      Relay
	lastConfig time.Time
	ttl        time.Duration
	stun       map[[12]byte]stunRequest
	ownPool    netip.Prefix
}
type Relay interface {
	Send(context.Context, ID, []byte) error
	Connected() bool
}

func NewBind(own ID) *Bind {
	return &Bind{own: own, peers: map[ID]*peerState{}, pending: map[[8]byte]pendingProbe{}, in: make(chan received, 256), done: make(chan struct{}), stun: map[[12]byte]stunRequest{}}
}
func (b *Bind) SetRelay(r Relay) { b.mu.Lock(); b.relay = r; b.mu.Unlock() }
func (b *Bind) ReplacePeers(c NetworkConfig) {
	b.mu.Lock()
	defer b.mu.Unlock()
	next := map[ID]*peerState{}
	if ownIP, e := netip.ParseAddr(c.VirtualIP); e == nil && c.PrefixLength > 0 {
		b.ownPool = netip.PrefixFrom(ownIP.Unmap(), c.PrefixLength).Masked()
	}
	for _, p := range c.Peers {
		validCandidates := make([]Candidate, 0, len(p.Candidates))
		for _, candidate := range p.Candidates {
			if address, e := candidate.Addr(); e == nil {
				if _, allowed := normalizeDirectAddress(address.Addr(), b.ownPool, true); allowed {
					validCandidates = append(validCandidates, candidate)
				}
			}
		}
		p.Candidates = validCandidates
		id, _ := ParseID(p.PeerID)
		key, _ := decodeKey(p.PairSecret)
		old, ok := b.peers[id]
		if ok && old.key == key && old.config.PublicKey == p.PublicKey {
			old.config = p
			next[id] = old
		} else {
			next[id] = &peerState{config: p, id: id, key: key, routes: map[string]route{}, seen: nonceCache{}}
		}
	}
	b.peers = next
	b.pending = map[[8]byte]pendingProbe{}
	b.lastConfig = time.Now()
	b.ttl = time.Duration(c.TTLSeconds) * time.Second
}
func (b *Bind) configFreshLocked() bool {
	if !b.lastConfig.IsZero() && time.Since(b.lastConfig) >= b.ttl {
		b.peers = map[ID]*peerState{}
		b.pending = map[[8]byte]pendingProbe{}
		b.lastConfig = time.Time{}
	}
	return !b.lastConfig.IsZero()
}
func (b *Bind) Expire() {
	b.mu.Lock()
	b.peers = map[ID]*peerState{}
	b.pending = map[[8]byte]pendingProbe{}
	b.lastConfig = time.Time{}
	b.mu.Unlock()
}
func (b *Bind) BatchSize() int { return 1 }
func (b *Bind) SetMark(mark uint32) error {
	if mark != 0 {
		return errors.New("custom bind does not support packet marks")
	}
	return nil
}
func (b *Bind) ParseEndpoint(s string) (conn.Endpoint, error) {
	id, e := ParseID(s)
	if e != nil {
		return nil, e
	}
	b.mu.Lock()
	defer b.mu.Unlock()
	if !b.configFreshLocked() {
		return nil, errors.New("peer configuration expired")
	}
	p, ok := b.peers[id]
	if !ok {
		return nil, errors.New("endpoint is not an authorized peer")
	}
	a, _ := netip.ParseAddr(p.config.VirtualIP)
	return &virtualEndpoint{id: id, ip: a}, nil
}
func (b *Bind) Open(port uint16) ([]conn.ReceiveFunc, uint16, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.opened && !b.closed {
		return nil, 0, conn.ErrBindAlreadyOpen
	}
	u, e := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4zero, Port: int(port)})
	if e != nil {
		return nil, 0, e
	}
	b.udp = u
	b.opened = true
	b.closed = false
	b.done = make(chan struct{})
	b.in = make(chan received, 256)
	go b.readUDP(u, b.done)
	go b.probeLoop(b.done)
	return []conn.ReceiveFunc{b.receive}, uint16(u.LocalAddr().(*net.UDPAddr).Port), nil
}
func (b *Bind) Close() error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if !b.opened || b.closed {
		return nil
	}
	b.closed = true
	close(b.done)
	return b.udp.Close()
}
func (b *Bind) Port() uint16 {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.udp == nil {
		return 0
	}
	return uint16(b.udp.LocalAddr().(*net.UDPAddr).Port)
}
func (b *Bind) receive(packets [][]byte, sizes []int, eps []conn.Endpoint) (int, error) {
	select {
	case <-b.done:
		return 0, net.ErrClosed
	case p := <-b.in:
		if len(packets) == 0 || len(sizes) == 0 || len(eps) == 0 || len(packets[0]) < len(p.payload) {
			return 0, errors.New("receive buffer too short")
		}
		copy(packets[0], p.payload)
		sizes[0] = len(p.payload)
		eps[0] = &virtualEndpoint{id: p.id, ip: p.ip}
		return 1, nil
	}
}
func (b *Bind) Send(bufs [][]byte, endpoint conn.Endpoint) error {
	ep, ok := endpoint.(*virtualEndpoint)
	if !ok {
		return conn.ErrWrongEndpointType
	}
	for _, payload := range bufs {
		b.mu.Lock()
		p, ok := b.peers[ep.id]
		if !ok || !b.configFreshLocked() {
			b.mu.Unlock()
			return errors.New("peer configuration expired")
		}
		r, known := chooseRoute(p.routes, p.current, time.Now())
		if known {
			p.current = r.key()
		}
		key := p.key
		relay := b.relay
		u := b.udp
		closed := b.closed
		b.mu.Unlock()
		if closed || u == nil {
			return net.ErrClosed
		}
		nonce, e := randomNonce()
		if e != nil {
			return e
		}
		frame, e := packFrame(envelope{kind: frameData, src: b.own, dst: ep.id, at: time.Now().UnixMilli(), nonce: nonce, payload: payload}, key)
		if e != nil {
			return e
		}
		if known && !r.relay {
			if _, e = u.WriteToUDPAddrPort(frame, r.address); e == nil {
				continue
			}
			b.invalidateRoute(ep.id, r.key())
		}
		if relay == nil || !relay.Connected() {
			return errors.New("no live direct path or relay")
		}
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		e = relay.Send(ctx, ep.id, frame)
		cancel()
		if e != nil {
			return e
		}
	}
	return nil
}
func (b *Bind) invalidateRoute(id ID, key string) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if p := b.peers[id]; p != nil {
		delete(p.routes, key)
	}
}
func (b *Bind) readUDP(u *net.UDPConn, done <-chan struct{}) {
	buf := make([]byte, 4096)
	for {
		n, addr, e := u.ReadFromUDPAddrPort(buf)
		if e != nil {
			return
		}
		addr = netip.AddrPortFrom(addr.Addr().Unmap(), addr.Port())
		packet := append([]byte(nil), buf[:n]...)
		if b.handleSTUN(packet, addr) {
			continue
		}
		if n < frameHeader+frameMAC {
			continue
		}
		var src ID
		copy(src[:], packet[5:21])
		b.handleFrame(src, packet, addr, false)
	}
}
func (b *Bind) ReceiveRelay(src ID, packet []byte) {
	b.handleFrame(src, packet, netip.AddrPort{}, true)
}
func (b *Bind) handleFrame(source ID, packet []byte, address netip.AddrPort, isRelay bool) {
	now := time.Now()
	b.mu.Lock()
	if !isRelay {
		if _, allowed := normalizeDirectAddress(address.Addr(), b.ownPool, true); !allowed {
			b.mu.Unlock()
			return
		}
	}
	p := b.peers[source]
	if p == nil || !b.configFreshLocked() {
		b.mu.Unlock()
		return
	}
	f, e := unpackFrame(packet, p.key, b.own, source, now)
	if e != nil {
		b.mu.Unlock()
		return
	}
	if f.kind == frameReply {
		pending, ok := b.pending[f.nonce]
		if !ok || pending.peer != source || pending.relay != isRelay || now.Sub(pending.at) > 5*time.Second {
			b.mu.Unlock()
			return
		}
		delete(b.pending, f.nonce)
		r := route{address: address, relay: isRelay, rtt: now.Sub(pending.at), confirmed: now}
		key := r.key()
		if old, ok := p.routes[key]; ok {
			r.rtt = (3*old.rtt + r.rtt) / 4
		}
		p.routes[key] = r
		b.mu.Unlock()
		return
	}
	if f.kind == frameProbe && !p.seen.accept(f.nonce, now) {
		b.mu.Unlock()
		return
	}
	key := p.key
	ip, _ := netip.ParseAddr(p.config.VirtualIP)
	relay := b.relay
	u := b.udp
	if f.kind == frameProbe && !isRelay { // Authentication permits learning a roaming source; RTT still needs a reply.
		found := false
		for _, c := range p.config.Candidates {
			a, _ := c.Addr()
			if a == address {
				found = true
			}
		}
		if !found && len(p.config.Candidates) < 32 {
			p.config.Candidates = append(p.config.Candidates, Candidate{IP: address.Addr().String(), Port: address.Port()})
		}
	}
	b.mu.Unlock()
	if f.kind == frameProbe {
		reply, e := packFrame(envelope{kind: frameReply, src: b.own, dst: source, at: now.UnixMilli(), nonce: f.nonce}, key)
		if e != nil {
			return
		}
		if isRelay {
			if relay != nil {
				ctx, cancel := context.WithTimeout(context.Background(), time.Second)
				_ = relay.Send(ctx, source, reply)
				cancel()
			}
		} else if u != nil {
			_, _ = u.WriteToUDPAddrPort(reply, address)
		}
		return
	}
	if f.kind == frameData {
		select {
		case b.in <- received{payload: append([]byte(nil), f.payload...), id: source, ip: ip}:
		default:
		}
	}
}
func (b *Bind) probeLoop(done <-chan struct{}) {
	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	b.Probe()
	for {
		select {
		case <-done:
			return
		case <-ticker.C:
			b.Probe()
		}
	}
}
func (b *Bind) Probe() {
	now := time.Now()
	type task struct {
		id    ID
		key   [32]byte
		addr  netip.AddrPort
		relay bool
	}
	var tasks []task
	b.mu.Lock()
	if !b.configFreshLocked() {
		b.mu.Unlock()
		return
	}
	for n, p := range b.pending {
		if now.Sub(p.at) > 5*time.Second {
			delete(b.pending, n)
		}
	}
	for _, p := range b.peers {
		for _, c := range p.config.Candidates {
			a, e := c.Addr()
			if e == nil {
				tasks = append(tasks, task{p.id, p.key, a, false})
			}
		}
		if b.relay != nil && b.relay.Connected() {
			tasks = append(tasks, task{p.id, p.key, netip.AddrPort{}, true})
		}
	}
	b.mu.Unlock()
	for _, t := range tasks {
		nonce, e := randomNonce()
		if e != nil {
			return
		}
		frame, _ := packFrame(envelope{kind: frameProbe, src: b.own, dst: t.id, at: now.UnixMilli(), nonce: nonce}, t.key)
		b.mu.Lock()
		b.pending[nonce] = pendingProbe{peer: t.id, address: t.addr, relay: t.relay, at: now}
		u := b.udp
		r := b.relay
		b.mu.Unlock()
		if t.relay {
			ctx, cancel := context.WithTimeout(context.Background(), time.Second)
			_ = r.Send(ctx, t.id, frame)
			cancel()
		} else if u != nil {
			_, _ = u.WriteToUDPAddrPort(frame, t.addr)
		}
	}
}
func (b *Bind) Status() []PeerStatus {
	b.mu.Lock()
	defer b.mu.Unlock()
	out := make([]PeerStatus, 0, len(b.peers))
	fresh := b.configFreshLocked()
	for _, p := range b.peers {
		s := PeerStatus{PeerID: p.id.String(), IP: p.config.VirtualIP, Path: "offline"}
		if fresh {
			s.Path = "probing"
			r, ok := chooseRoute(p.routes, p.current, time.Now())
			if ok {
				v := float64(r.rtt) / float64(time.Millisecond)
				s.RTTMs = &v
				if r.relay {
					s.Path = "relay"
				} else {
					s.Path = "direct"
				}
			}
		}
		out = append(out, s)
	}
	return out
}
