//go:build windows

package agent

import (
	"fmt"
	"net/netip"
	"os"
	"path/filepath"
	"strings"
)

func interfaceName() string { return "R-Link Fabric" }
func configureInterface(name, ip string, bits int) (func(), error) {
	a, e := netip.ParseAddr(ip)
	if e != nil {
		return nil, e
	}
	prefix := netip.PrefixFrom(a, bits).Masked().String()
	if strings.ContainsAny(name, "'\r\n") {
		return nil, fmt.Errorf("invalid TUN name")
	}
	// Fixed PowerShell program with validated IP/adapter values. No default
	// route or DNS setting is added, and existing foreign routes are preserved.
	program := fmt.Sprintf("$ErrorActionPreference='Stop'; $a=Get-NetAdapter -Name '%s'; $other=Get-NetRoute -DestinationPrefix '%s' -ErrorAction SilentlyContinue | Where-Object InterfaceIndex -ne $a.ifIndex; if($other){throw 'Virtual subnet route conflict'}; New-NetIPAddress -InterfaceIndex $a.ifIndex -IPAddress '%s' -PrefixLength 32 | Out-Null; Set-NetIPInterface -InterfaceIndex $a.ifIndex -AddressFamily IPv4 -NlMtuBytes 1280; New-NetRoute -InterfaceIndex $a.ifIndex -DestinationPrefix '%s' -NextHop '0.0.0.0' -RouteMetric 5 | Out-Null", name, prefix, ip, prefix)
	path := filepath.Join(os.Getenv("SystemRoot"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
	if e = command(path, "-NoProfile", "-NonInteractive", "-Command", program); e != nil {
		return nil, e
	}
	return func() {}, nil
}
