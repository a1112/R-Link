package agent

import (
	"net"
	"net/netip"
	"strings"
)

var (
	cgnatPrefix     = netip.MustParsePrefix("100.64.0.0/10")
	benchmarkPrefix = netip.MustParsePrefix("198.18.0.0/15")
)

func normalizeDirectAddress(ip netip.Addr, ownPool netip.Prefix, allowLoopback bool) (netip.Addr, bool) {
	ip = ip.Unmap()
	if !ip.Is4() || ip.IsUnspecified() || ip.IsMulticast() || ip.IsLinkLocalUnicast() || ip == netip.MustParseAddr("255.255.255.255") || (!allowLoopback && ip.IsLoopback()) || cgnatPrefix.Contains(ip) || benchmarkPrefix.Contains(ip) || (ownPool.IsValid() && ownPool.Contains(ip)) {
		return ip, false
	}
	return ip, true
}

// Interface names are only one signal: renamed overlays can retain an ordinary
// Ethernet name. A LAN candidate must also have link-layer identity and avoid
// point-to-point flags, CGNAT overlay ranges, and the assigned fabric subnet.
func candidateInterfaceAllowed(iface net.Interface) bool {
	if iface.Flags&net.FlagUp == 0 || iface.Flags&(net.FlagLoopback|net.FlagPointToPoint) != 0 || len(iface.HardwareAddr) != 6 {
		return false
	}
	allZero, allOnes := true, true
	for _, b := range iface.HardwareAddr {
		allZero = allZero && b == 0
		allOnes = allOnes && b == 255
	}
	if allZero || allOnes {
		return false
	}
	name := strings.ToLower(iface.Name)
	for _, token := range []string{"rlink", "r-link", "netbird", "tailscale", "clash", "mihomo", "wintun", "wireguard", "utun", "tun", "tap", "vethernet", "docker", "veth", "bridge", "virbr", "vmnet", "vmware", "virtualbox", "zerotier", "openvpn", "vpn", "hyper-v", "wsl"} {
		if strings.Contains(name, token) {
			return false
		}
	}
	if strings.HasPrefix(name, "wg") || strings.HasPrefix(name, "br-") || name == "br0" {
		return false
	}
	return true
}

func interfaceCandidates(iface net.Interface, addresses []string, port uint16, ownPool netip.Prefix) []Candidate {
	if port == 0 || !candidateInterfaceAllowed(iface) {
		return nil
	}
	var out []Candidate
	seen := map[netip.Addr]bool{}
	for _, address := range addresses {
		prefix, e := netip.ParsePrefix(address)
		if e != nil {
			continue
		}
		ip, allowed := normalizeDirectAddress(prefix.Addr(), ownPool, false)
		if !allowed || seen[ip] {
			continue
		}
		seen[ip] = true
		out = append(out, Candidate{IP: ip.String(), Port: port, Source: "lan"})
	}
	return out
}
