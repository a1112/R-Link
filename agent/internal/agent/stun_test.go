package agent

import (
	"context"
	"net"
	"testing"
	"time"
)

func TestOwnSTUNObservesSameUDPMapping(t *testing.T) {
	// The production server consumes a pre-bound socket; the kernel queues the
	// first request even if the test goroutine has not yet been scheduled.
	socket, e := net.ListenUDP("udp4", &net.UDPAddr{IP: net.IPv4(127, 0, 0, 1)})
	if e != nil {
		t.Fatal(e)
	}
	address := socket.LocalAddr().String()
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- serveSTUNConn(ctx, socket) }()
	b := NewBind(testID(1))
	if _, _, e = b.Open(0); e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	lookup, cancelLookup := context.WithTimeout(ctx, 2*time.Second)
	defer cancelLookup()
	candidate, e := b.Discover(lookup, "stun:"+address)
	if e != nil {
		t.Fatal(e)
	}
	if candidate.IP != "127.0.0.1" || candidate.Port != b.Port() {
		t.Fatalf("mapped candidate disagrees with data socket: %+v", candidate)
	}
	cancel()
	if e = <-done; e != nil {
		t.Fatal(e)
	}
}
