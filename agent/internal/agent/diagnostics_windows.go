//go:build windows

package agent

import "golang.org/x/sys/windows/svc/eventlog"

func recordStartupEvent(stage, code string) {
	log, e := eventlog.Open("RLinkFabric")
	if e != nil {
		return
	}
	defer log.Close()
	_ = log.Error(1001, "R-Link Agent startup failed; stage="+stage+"; code="+code)
}
