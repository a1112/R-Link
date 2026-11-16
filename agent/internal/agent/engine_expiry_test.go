package agent

import (
	"bytes"
	"encoding/hex"
	"strings"
	"testing"
	"time"
)

// Exercise expiry and recovery with actual WireGuard devices and memory TUNs.
// This is not a privileged OS TUN or full control-loop integration test.
func TestWireGuardRecoversAfterConfigurationExpiry(t *testing.T) {

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
	{
		// This test targets data paths, not startup timers. Avoid spending most of
		// its payload deadline on keepalive's initial handshake before routes exist.
		for _, peer := range []struct {
			engine *Engine
			remote Identity
		}{{ea, c}, {ec, a}} {
			key, err := decodeKey(peer.remote.PublicKey)
			if err != nil {
				t.Fatal(err)
			}
			if err = peer.engine.device.IpcSet("public_key=" + hex.EncodeToString(key[:]) + "\npersistent_keepalive_interval=0\n"); err != nil {
				t.Fatal(err)
			}
		}
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
	waitFor(t, func() bool {
		return len(ba.Status()) == 1 && ba.Status()[0].Path == "direct" && len(bc.Status()) == 1 && bc.Status()[0].Path == "direct"
	})
	deliver := func(payload string) {
		t.Helper()
		packet := ipv4Packet(payload)
		ta.in <- packet
		select {
		case got := <-tc.out:
			if !bytes.Equal(got, packet) {
				t.Fatal("decrypted payload mismatch")
			}
		case <-time.After(8 * time.Second):
			t.Fatal("decrypted payload not delivered")
		}
	}
	deliver("before expiry")
	before := ba.Status()
	ea.FillStatus(before)
	if before[0].LastHandshake == 0 || before[0].TxBytes == 0 {
		t.Fatal("real handshake/counter evidence missing")
	}
	endpoint, err := ba.ParseEndpoint(c.PeerID)
	if err != nil {
		t.Fatal(err)
	}
	ba.Expire()
	ea.Expire()
	if err := ba.Send([][]byte{[]byte("expired synthetic payload")}, endpoint); err == nil || !strings.Contains(err.Error(), "expired") {
		t.Fatalf("expired send: %v", err)
	}
	if len(ba.Status()) != 0 {
		t.Fatal("expired bind retained peers")
	}
	state, err := ea.device.IpcGet()
	if err != nil || strings.Contains(state, "public_key=") {
		t.Fatalf("WireGuard peers retained: %v", err)
	}
	ta.in <- ipv4Packet("not delivered while expired")
	select {
	case <-tc.out:
		t.Fatal("expired packet delivered")
	case <-time.After(300 * time.Millisecond):
	}
	ba.ReplacePeers(ca)
	ba.Probe()
	bc.Probe()
	// Establish the transport before reapplying WireGuard. This isolated test
	// checks removal/recovery, not handshake retry timing or runtime ordering.
	waitFor(t, func() bool { return len(ba.Status()) == 1 && ba.Status()[0].Path == "direct" })
	if err := ea.Apply(ca); err != nil {
		t.Fatal(err)
	}
	deliver("after fresh configuration")
	after := ba.Status()
	ea.FillStatus(after)
	if after[0].LastHandshake == 0 || after[0].TxBytes == 0 {
		t.Fatal("recovered handshake/counter evidence missing")
	}
}
