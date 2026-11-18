package agent

import (
	"strings"
	"testing"
	"testing/synctest"
	"time"
)

// The configuration keeps its valid production TTL; synctest advances only
// this test's clock. No sockets, OS TUN, control server or production identity.
func TestBindAuthorizationTTLBoundaryAndRecovery(t *testing.T) {
	synctest.Test(t, func(t *testing.T) {
		a, b := testIdentity(t, testID(1), "10.253.199.2"), testIdentity(t, testID(2), "10.253.199.3")
		n := testConfig(a, b, testKey(7))
		n.TTLSeconds = 15
		if err := n.Validate(a); err != nil {
			t.Fatal(err)
		}
		bind := NewBind(testID(1))
		bind.ReplacePeers(n)
		endpoint, err := bind.ParseEndpoint(b.PeerID)
		if err != nil {
			t.Fatal(err)
		}
		time.Sleep(15*time.Second - time.Nanosecond)
		if _, err := bind.ParseEndpoint(b.PeerID); err != nil {
			t.Fatalf("expired before TTL: %v", err)
		}
		if len(bind.Status()) != 1 {
			t.Fatal("peer removed before TTL")
		}
		time.Sleep(time.Nanosecond)
		if err := bind.Send([][]byte{[]byte("synthetic")}, endpoint); err == nil || !strings.Contains(err.Error(), "expired") {
			t.Fatalf("stale endpoint send: %v", err)
		}
		if len(bind.Status()) != 0 {
			t.Fatal("peer retained at TTL")
		}
		if _, err := bind.ParseEndpoint(b.PeerID); err == nil {
			t.Fatal("expired endpoint accepted")
		}
		bind.ReplacePeers(n)
		if _, err := bind.ParseEndpoint(b.PeerID); err != nil {
			t.Fatalf("fresh config not restored: %v", err)
		}
		if s := bind.Status(); len(s) != 1 || s[0].Path != "probing" {
			t.Fatalf("restored status: %+v", s)
		}
	})
}
