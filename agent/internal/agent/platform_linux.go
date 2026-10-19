//go:build linux

package agent

import (
	"fmt"
	"net/netip"
)

func interfaceName() string { return "rlink0" }
func configureInterface(name, ip string, bits int) (func(), error) {
	a, e := netip.ParseAddr(ip)
	if e != nil {
		return nil, e
	}
	prefix := netip.PrefixFrom(a, bits).Masked().String()
	address := ip + "/32"
	path := "/usr/sbin/ip"
	if e = command(path, "address", "add", address, "dev", name); e != nil {
		return nil, e
	}
	if e = command(path, "link", "set", "dev", name, "mtu", "1280", "up"); e != nil {
		return nil, e
	}
	if e = command(path, "route", "add", prefix, "dev", name, "src", ip); e != nil {
		return nil, fmt.Errorf("virtual subnet route conflicts with an existing route")
	}
	return func() { _ = command(path, "route", "del", prefix, "dev", name) }, nil
}
