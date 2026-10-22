package agent

import (
	"net/netip"
	"time"
)

const pathExpiry = 12 * time.Second

type route struct {
	address   netip.AddrPort
	relay     bool
	rtt       time.Duration
	confirmed time.Time
}

func (r route) key() string {
	if r.relay {
		return "relay"
	}
	return r.address.String()
}
func (r route) fresh(now time.Time) bool {
	return !r.confirmed.IsZero() && now.Sub(r.confirmed) < pathExpiry
}

// Select the measured shortest route. Changing a live route requires a 20%
// improvement or 2 ms improvement (whichever is greater) to avoid oscillation.
func chooseRoute(routes map[string]route, current string, now time.Time) (route, bool) {
	var best route
	found := false
	for _, r := range routes {
		if !r.fresh(now) {
			continue
		}
		if !found || r.rtt < best.rtt || r.rtt == best.rtt && !r.relay {
			best = r
			found = true
		}
	}
	if !found {
		return route{}, false
	}
	old, ok := routes[current]
	if ok && old.fresh(now) && best.key() != current {
		margin := old.rtt / 5
		if margin < 2*time.Millisecond {
			margin = 2 * time.Millisecond
		}
		if old.rtt-best.rtt < margin {
			return old, true
		}
	}
	return best, true
}
