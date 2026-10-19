//go:build windows

package main

import (
	"context"
	"os"

	"golang.org/x/sys/windows/svc"
)

func dispatch() error {
	if len(os.Args) > 1 && os.Args[1] == "run" {
		isService, e := svc.IsWindowsService()
		if e != nil {
			return e
		}
		if isService {
			return svc.Run("RLinkFabric", serviceHandler{})
		}
	}
	return run(context.Background())
}

type serviceHandler struct{}

func (serviceHandler) Execute(_ []string, requests <-chan svc.ChangeRequest, status chan<- svc.Status) (bool, uint32) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	status <- svc.Status{State: svc.StartPending}
	done := make(chan error, 1)
	go func() { done <- run(ctx) }()
	status <- svc.Status{State: svc.Running, Accepts: svc.AcceptStop | svc.AcceptShutdown}
	for {
		select {
		case e := <-done:
			if e != nil {
				return true, 1
			}
			return false, 0
		case change := <-requests:
			switch change.Cmd {
			case svc.Stop, svc.Shutdown:
				status <- svc.Status{State: svc.StopPending}
				cancel()
				e := <-done
				if e != nil {
					return true, 1
				}
				return false, 0
			case svc.Interrogate:
				status <- change.CurrentStatus
			}
		}
	}
}
