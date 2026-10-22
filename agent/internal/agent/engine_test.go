package agent

import (
	"bytes"
	"context"
	"crypto/ecdh"
	"crypto/rand"
	"encoding/base64"
	"encoding/binary"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/gorilla/websocket"
	"golang.zx2c4.com/wireguard/tun"
)

type memoryTUN struct {
	in, out chan []byte
	done    chan struct{}
	events  chan tun.Event
	once    sync.Once
}

func newMemoryTUN() *memoryTUN {
	return &memoryTUN{in: make(chan []byte, 8), out: make(chan []byte, 8), done: make(chan struct{}), events: make(chan tun.Event, 1)}
}
func (t *memoryTUN) File() *os.File           { return nil }
func (t *memoryTUN) Name() (string, error)    { return "test-only-tun", nil }
func (t *memoryTUN) MTU() (int, error)        { return 1280, nil }
func (t *memoryTUN) Events() <-chan tun.Event { return t.events }
func (t *memoryTUN) BatchSize() int           { return 1 }
func (t *memoryTUN) Close() error             { t.once.Do(func() { close(t.done); close(t.events) }); return nil }
func (t *memoryTUN) Read(bufs [][]byte, sizes []int, offset int) (int, error) {
	select {
	case <-t.done:
		return 0, io.EOF
	case b := <-t.in:
		copy(bufs[0][offset:], b)
		sizes[0] = len(b)
		return 1, nil
	}
}
func (t *memoryTUN) Write(bufs [][]byte, offset int) (int, error) {
	for _, b := range bufs {
		select {
		case <-t.done:
			return 0, io.EOF
		case t.out <- append([]byte(nil), b[offset:]...):
		}
	}
	return len(bufs), nil
}

func testIdentity(t *testing.T, id ID, ip string) Identity {
	t.Helper()
	k, e := ecdh.X25519().GenerateKey(rand.Reader)
	if e != nil {
		t.Fatal(e)
	}
	return Identity{PeerID: id.String(), Name: "integration", ControlURL: "https://example.test/r-link", PrivateKey: base64.StdEncoding.EncodeToString(k.Bytes()), PublicKey: base64.StdEncoding.EncodeToString(k.PublicKey().Bytes()), VirtualIP: ip, PrefixLength: 24}
}
func testConfig(i, other Identity, key [32]byte) NetworkConfig {
	return NetworkConfig{PeerID: i.PeerID, PublicKey: i.PublicKey, VirtualIP: i.VirtualIP, PrefixLength: 24, TTLSeconds: 45, HeartbeatInterval: 15, RelayURL: "wss://example.test/r-link/api/fabric/relay", Peers: []PeerConfig{{PeerID: other.PeerID, PublicKey: other.PublicKey, VirtualIP: other.VirtualIP, PairSecret: base64.StdEncoding.EncodeToString(key[:])}}}
}
func waitFor(t *testing.T, fn func() bool) {
	t.Helper()
	deadline := time.Now().Add(8 * time.Second)
	for time.Now().Before(deadline) {
		if fn() {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatal("condition timed out")
}
func ipv4Packet(payload string) []byte {
	b := make([]byte, 28+len(payload))
	b[0] = 0x45
	binary.BigEndian.PutUint16(b[2:4], uint16(len(b)))
	b[8] = 64
	b[9] = 17
	copy(b[12:16], []byte{10, 253, 199, 2})
	copy(b[16:20], []byte{10, 253, 199, 3})
	binary.BigEndian.PutUint16(b[20:22], 9000)
	binary.BigEndian.PutUint16(b[22:24], 9001)
	binary.BigEndian.PutUint16(b[24:26], uint16(len(b)-20))
	copy(b[28:], payload)
	var sum uint32
	for x := 0; x < 20; x += 2 {
		sum += uint32(binary.BigEndian.Uint16(b[x : x+2]))
	}
	for sum > 65535 {
		sum = (sum & 65535) + (sum >> 16)
	}
	binary.BigEndian.PutUint16(b[10:12], ^uint16(sum))
	return b
}

func TestWireGuardEncryptedDirectThenRealWebSocketRelay(t *testing.T) {
	a, c := testIdentity(t, testID(1), "10.253.199.2"), testIdentity(t, testID(2), "10.253.199.3")
	ca, cc := testConfig(a, c, testKey(7)), testConfig(c, a, testKey(7))
	ba, bc := NewBind(testID(1)), NewBind(testID(2))
	ba.ReplacePeers(ca)
	bc.ReplacePeers(cc)
	ta, tc := newMemoryTUN(), newMemoryTUN()
	ea, e := newEngineWithTUN(a, ba, ta, "simulated", nil)
	if e != nil {
		t.Fatal(e)
	}
	defer ea.Close()
	ec, e := newEngineWithTUN(c, bc, tc, "simulated", nil)
	if e != nil {
		t.Fatal(e)
	}
	defer ec.Close()
	if e = ea.Apply(ca); e != nil {
		t.Fatal(e)
	}
	if e = ec.Apply(cc); e != nil {
		t.Fatal(e)
	}
	if e = ea.Up(); e != nil {
		t.Fatal(e)
	}
	if e = ec.Up(); e != nil {
		t.Fatal(e)
	}
	ca.Peers[0].Candidates = []Candidate{{IP: "127.0.0.1", Port: bc.Port()}}
	cc.Peers[0].Candidates = []Candidate{{IP: "127.0.0.1", Port: ba.Port()}}
	ba.ReplacePeers(ca)
	bc.ReplacePeers(cc)
	ba.Probe()
	bc.Probe()
	waitFor(t, func() bool { return len(ba.Status()) == 1 && ba.Status()[0].Path == "direct" })
	packet := ipv4Packet("the direct payload is encrypted by WireGuard")
	ta.in <- packet
	select {
	case got := <-tc.out:
		if !bytes.Equal(got, packet) {
			t.Fatal("decrypted direct packet mismatch")
		}
	case <-time.After(8 * time.Second):
		t.Fatal("real WireGuard direct handshake/packet failed")
	}
	s := ba.Status()
	ea.FillStatus(s)
	if s[0].LastHandshake == 0 || s[0].TxBytes == 0 {
		t.Fatal("actual WireGuard handshake/counter missing")
	}
	// An actual WebSocket server only forwards opaque envelopes, using socket
	// identity for the outer source UUID. It never sees decrypted IP packets.
	var mu sync.Mutex
	connections := map[ID]*websocket.Conn{}
	upgrader := websocket.Upgrader{CheckOrigin: func(*http.Request) bool { return true }}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		id := testID(1)
		if r.Header.Get("Authorization") == "Bearer b" {
			id = testID(2)
		}
		ws, e := upgrader.Upgrade(w, r, nil)
		if e != nil {
			return
		}
		defer ws.Close()
		mu.Lock()
		connections[id] = ws
		mu.Unlock()
		defer func() { mu.Lock(); delete(connections, id); mu.Unlock() }()
		for {
			kind, raw, e := ws.ReadMessage()
			if e != nil {
				return
			}
			if kind != websocket.BinaryMessage || len(raw) < 16 {
				continue
			}
			var dst ID
			copy(dst[:], raw[:16])
			forward := append(append([]byte(nil), id[:]...), raw[16:]...)
			mu.Lock()
			peer := connections[dst]
			if peer != nil {
				if bytes.Contains(raw, []byte("relay payload")) {
					t.Error("plaintext leaked into relay")
				}
				_ = peer.WriteMessage(websocket.BinaryMessage, forward)
			}
			mu.Unlock()
		}
	}))
	defer server.Close()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	ra, rc := NewWSRelay("ws"+strings.TrimPrefix(server.URL, "http"), "a", ba), NewWSRelay("ws"+strings.TrimPrefix(server.URL, "http"), "b", bc)
	ba.SetRelay(ra)
	bc.SetRelay(rc)
	defer ra.Close()
	defer rc.Close()
	go ra.Run(ctx)
	go rc.Run(ctx)
	waitFor(t, func() bool { return ra.Connected() && rc.Connected() })
	ba.Probe()
	bc.Probe()
	waitFor(t, func() bool {
		ba.mu.Lock()
		defer ba.mu.Unlock()
		r, ok := ba.peers[testID(2)].routes["relay"]
		return ok && r.fresh(time.Now())
	})
	for _, b := range []*Bind{ba, bc} {
		b.mu.Lock()
		for _, p := range b.peers {
			p.config.Candidates = nil
			for k, r := range p.routes {
				if !r.relay {
					r.confirmed = time.Now().Add(-20 * time.Second)
					p.routes[k] = r
				}
			}
		}
		b.mu.Unlock()
	}
	packet = ipv4Packet("the relay payload is also end-to-end encrypted")
	ta.in <- packet
	select {
	case got := <-tc.out:
		if !bytes.Equal(got, packet) {
			t.Fatal("decrypted relay packet mismatch")
		}
	case <-time.After(8 * time.Second):
		t.Fatal("WireGuard automatic relay fallback failed")
	}
	if ba.Status()[0].Path != "relay" {
		t.Fatal("relay failover status missing")
	}
	ba.Expire()
	if _, e = ba.ParseEndpoint(c.PeerID); e == nil {
		t.Fatal("revoked peer retained after configuration expiry")
	}
}

func TestConfigRejectsForeignOriginIdentityAndSubnet(t *testing.T) {
	a, b := testIdentity(t, testID(1), "10.253.199.2"), testIdentity(t, testID(2), "10.253.199.3")
	n := testConfig(a, b, testKey(7))
	if e := n.Validate(a); e != nil {
		t.Fatal(e)
	}
	n.RelayURL = "wss://evil.test/r-link/api/fabric/relay"
	if n.Validate(a) == nil {
		t.Fatal("foreign relay origin accepted")
	}
	n = testConfig(a, b, testKey(7))
	n.VirtualIP = "10.253.199.99"
	if n.Validate(a) == nil {
		t.Fatal("changed own IP accepted")
	}
	n = testConfig(a, b, testKey(7))
	n.Peers[0].VirtualIP = "10.2.1.1"
	if n.Validate(a) == nil {
		t.Fatal("foreign subnet peer accepted")
	}
	n = testConfig(a, b, testKey(7))
	n.TTLSeconds = 3600
	if n.Validate(a) == nil {
		t.Fatal("unsafe authorization TTL accepted")
	}
}
