package agent

import (
	"net"
	"net/netip"
	"testing"
	"time"
)

func fixtureInterface(name string) net.Interface {
	return net.Interface{Name: name, HardwareAddr: net.HardwareAddr{0x52, 0x54, 0x00, 0x12, 0x34, 0x56}, Flags: net.FlagUp | net.FlagBroadcast | net.FlagMulticast}
}
func TestCandidateCollectionPreservesPhysicalLinksAndRejectsOverlays(t *testing.T) {
	pool := netip.MustParsePrefix("10.253.199.0/24")
	fixtures := []struct {
		name      string
		addresses []string
		expected  string
	}{
		{"Wi-Fi", []string{"::ffff:192.168.1.241/120", "fe80::1/64"}, "192.168.1.241"},
		{"en0", []string{"192.168.1.50/24", "fe80::4%en0/64"}, "192.168.1.50"},
		{"eth0", []string{"10.0.0.16/24"}, "10.0.0.16"},
		{"NetBird", []string{"100.126.3.139/16"}, ""},
		{"Ethernet", []string{"100.126.3.139/10"}, ""}, // A renamed overlay remains excluded by range.
		{"Ethernet", []string{"10.253.199.2/24"}, ""},
		{"Ethernet", []string{"198.18.0.1/15"}, ""},
		{"Tailscale", []string{"192.168.88.1/24"}, ""},
		{"Clash", []string{"192.168.88.1/24"}, ""},
		{"Wintun", []string{"192.168.88.1/24"}, ""},
		{"utun9", []string{"192.168.88.1/24"}, ""},
		{"tun0", []string{"192.168.88.1/24"}, ""},
		{"wg0", []string{"192.168.88.1/24"}, ""},
		{"vEthernet (WSL)", []string{"192.168.88.1/24"}, ""},
		{"docker0", []string{"192.168.88.1/24"}, ""},
		{"veth0123", []string{"192.168.88.1/24"}, ""},
		{"bridge0", []string{"192.168.88.1/24"}, ""},
		{"br-a123", []string{"192.168.88.1/24"}, ""},
	}
	for _, fixture := range fixtures {
		t.Run(fixture.name+fixture.addresses[0], func(t *testing.T) {
			got := interfaceCandidates(fixtureInterface(fixture.name), fixture.addresses, 51822, pool)
			if fixture.expected == "" {
				if len(got) != 0 {
					t.Fatalf("overlay candidate leaked: %+v", got)
				}
			} else if len(got) != 1 || got[0].IP != fixture.expected {
				t.Fatalf("physical link candidate missing or not normalized: %+v", got)
			}
		})
	}
	unknown := fixtureInterface("renamed")
	unknown.HardwareAddr = nil
	if len(interfaceCandidates(unknown, []string{"192.168.88.1/24"}, 51822, pool)) != 0 {
		t.Fatal("MAC-less tunnel accepted")
	}
	unknown = fixtureInterface("renamed")
	unknown.Flags |= net.FlagPointToPoint
	if len(interfaceCandidates(unknown, []string{"192.168.88.1/24"}, 51822, pool)) != 0 {
		t.Fatal("renamed point-to-point tunnel accepted")
	}
}

func TestAuthenticatedOverlaySourceCannotBecomeDirectRoute(t *testing.T) {
	i, j := testIdentity(t, testID(1), "10.253.199.2"), testIdentity(t, testID(2), "10.253.199.3")
	n := testConfig(i, j, testKey(7))
	n.Peers[0].Candidates = []Candidate{{IP: "100.126.3.139", Port: 51822}, {IP: "10.253.199.3", Port: 51822}, {IP: "192.168.1.136", Port: 51822}}
	b := NewBind(testID(1))
	b.ReplacePeers(n)
	if got := b.peers[testID(2)].config.Candidates; len(got) != 1 || got[0].IP != "192.168.1.136" {
		t.Fatalf("old signaled overlay candidates retained: %+v", got)
	}
	for _, address := range []string{"100.126.3.139:51822", "10.253.199.3:51822", "198.18.0.1:51822"} {
		nonce, _ := randomNonce()
		raw, _ := packFrame(envelope{kind: frameProbe, src: testID(2), dst: testID(1), at: time.Now().UnixMilli(), nonce: nonce}, testKey(7))
		b.handleFrame(testID(2), raw, netip.MustParseAddrPort(address), false)
	}
	if len(b.peers[testID(2)].config.Candidates) != 1 {
		t.Fatal("authenticated overlay source bypassed candidate exclusion")
	}
	nonce, _ := randomNonce()
	raw, _ := packFrame(envelope{kind: frameProbe, src: testID(2), dst: testID(1), at: time.Now().UnixMilli(), nonce: nonce}, testKey(7))
	b.handleFrame(testID(2), raw, netip.MustParseAddrPort("192.168.1.200:51822"), false)
	if len(b.peers[testID(2)].config.Candidates) != 2 {
		t.Fatal("ordinary authenticated LAN roaming was disabled")
	}
}
