package agent

import (
	"bytes"
	"net/netip"
	"testing"
	"time"
)

func testID(v byte) ID { var id ID; id[15] = v; return id }
func testKey(v byte) [32]byte {
	var key [32]byte
	for i := range key {
		key[i] = v
	}
	return key
}
func TestAuthenticatedEnvelopeRejectsTamperingSourceAndReplay(t *testing.T) {
	now := time.Now()
	src, dst := testID(1), testID(2)
	key := testKey(9)
	n, _ := randomNonce()
	f := envelope{kind: frameData, src: src, dst: dst, at: now.UnixMilli(), nonce: n, payload: []byte("opaque encrypted packet")}
	raw, e := packFrame(f, key)
	if e != nil {
		t.Fatal(e)
	}
	out, e := unpackFrame(raw, key, dst, src, now)
	if e != nil || !bytes.Equal(out.payload, f.payload) {
		t.Fatal("valid authenticated envelope rejected")
	}
	tampered := append([]byte(nil), raw...)
	tampered[53] ^= 1
	if _, e = unpackFrame(tampered, key, dst, src, now); e == nil {
		t.Fatal("tampered payload accepted")
	}
	if _, e = unpackFrame(raw, key, dst, testID(3), now); e == nil {
		t.Fatal("forged relay source accepted")
	}
	if _, e = unpackFrame(raw, key, testID(3), src, now); e == nil {
		t.Fatal("wrong receiver accepted")
	}
	if _, e = unpackFrame(raw, key, dst, src, now.Add(31*time.Second)); e == nil {
		t.Fatal("expired envelope accepted")
	}
	cache := nonceCache{}
	if !cache.accept(n, now) || cache.accept(n, now) {
		t.Fatal("probe nonce replay accepted")
	}
}
func TestShortestMeasuredRouteUsesHysteresisAndExpires(t *testing.T) {
	now := time.Now()
	direct := route{address: netip.MustParseAddrPort("192.168.1.10:1234"), rtt: 10 * time.Millisecond, confirmed: now}
	relay := route{relay: true, rtt: 11 * time.Millisecond, confirmed: now}
	routes := map[string]route{direct.key(): direct, relay.key(): relay}
	selected, ok := chooseRoute(routes, "", now)
	if !ok || selected.relay {
		t.Fatal("lowest RTT direct route not chosen")
	}
	relay.rtt = 9 * time.Millisecond
	routes[relay.key()] = relay
	selected, _ = chooseRoute(routes, direct.key(), now)
	if selected.relay {
		t.Fatal("insufficient gain bypassed hysteresis")
	}
	relay.rtt = 5 * time.Millisecond
	routes[relay.key()] = relay
	selected, _ = chooseRoute(routes, direct.key(), now)
	if !selected.relay {
		t.Fatal("shorter relay route not selected")
	}
	direct.confirmed = now.Add(-13 * time.Second)
	routes[direct.key()] = direct
	selected, _ = chooseRoute(routes, direct.key(), now)
	if !selected.relay {
		t.Fatal("failed direct route not replaced by relay")
	}
	if _, ok = chooseRoute(routes, "", now.Add(13*time.Second)); ok {
		t.Fatal("expired path accepted")
	}
}
func TestUnauthenticatedUDPDoesNotLearnCandidate(t *testing.T) {
	self, peer := testID(1), testID(2)
	b := NewBind(self)
	p := PeerConfig{PeerID: peer.String(), VirtualIP: "10.253.199.2", PairSecret: ""}
	b.peers[peer] = &peerState{config: p, key: testKey(5), routes: map[string]route{}, seen: nonceCache{}}
	b.lastConfig = time.Now()
	b.ttl = time.Minute
	n, _ := randomNonce()
	frame, _ := packFrame(envelope{kind: frameProbe, src: peer, dst: self, at: time.Now().UnixMilli(), nonce: n}, testKey(6))
	b.handleFrame(peer, frame, netip.MustParseAddrPort("203.0.113.1:4444"), false)
	if len(b.peers[peer].config.Candidates) != 0 {
		t.Fatal("unauthenticated source was learned")
	}
}
