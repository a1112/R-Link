//go:build darwin

package agent

import "net/netip"

func interfaceName() string { return "utun" }
func configureInterface(name, ip string, bits int) (func(), error) {
	a, e := netip.ParseAddr(ip)
	if e != nil {
		return nil, e
	}
	prefix := netip.PrefixFrom(a, bits).Masked().String()
	if e = command("/sbin/ifconfig", name, "inet", ip, ip, "netmask", "255.255.255.255", "mtu", "1280", "up"); e != nil {
		return nil, e
	}
	if e = command("/sbin/route", "-n", "add", "-net", prefix, "-interface", name); e != nil {
		return nil, e
	}
	return func() { _ = command("/sbin/route", "-n", "delete", "-net", prefix, "-interface", name) }, nil
}
