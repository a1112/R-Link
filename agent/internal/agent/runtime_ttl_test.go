package agent

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

// This integration test intentionally uses the validated minimum 15-second TTL.
// The fast Bind boundary test covers exact deadlines without wall-clock sleeps.
func TestRuntimeHeartbeatSuccessDoesNotRenewConfigTTL(t *testing.T) {
	if testing.Short() {
		t.Skip("real control-loop TTL integration; run without -short")
	}
	a, b := testIdentity(t, testID(1), "10.253.199.2"), testIdentity(t, testID(2), "10.253.199.3")
	var recovering atomic.Bool
	var gets, beats atomic.Int32
	var n NetworkConfig
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/fabric/agent/config":
			count := gets.Add(1)
			if count > 1 && !recovering.Load() {
				http.Error(w, "synthetic config outage", 503)
				return
			}
			json.NewEncoder(w).Encode(n)
		case "/api/fabric/agent/heartbeat":
			beats.Add(1)
			w.Write([]byte("{\"config_version\":1}"))
		default:
			http.NotFound(w, r)
		}
	}))
	defer srv.Close()
	a.ControlURL = srv.URL
	a.DeviceToken = strings.Repeat("x", 32)
	n = testConfig(a, b, testKey(7))
	n.RelayURL = "ws" + strings.TrimPrefix(srv.URL, "http") + "/api/fabric/relay"
	n.TTLSeconds = 15
	n.HeartbeatInterval = 5
	n.ConfigVersion = 1
	dir := t.TempDir()
	config := filepath.Join(dir, "config.json")
	if e := SaveIdentity(config, a); e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan error, 1)
	go func() { done <- Run(ctx, config, true, 0, "") }()
	defer func() {
		cancel()
		select {
		case err := <-done:
			if err != nil {
				t.Errorf("runtime exit: %v", err)
			}
		case <-time.After(3 * time.Second):
			t.Error("runtime shutdown timeout")
		}
	}()
	read := func() PublicStatus {
		var s PublicStatus
		data, err := os.ReadFile(filepath.Join(dir, "status.json"))
		if errors.Is(err, os.ErrNotExist) {
			return s
		}
		if err != nil {
			t.Fatal(err)
		}
		if err := json.Unmarshal(data, &s); err != nil {
			t.Fatal(err)
		}
		return s
	}
	waitFor(t, func() bool { s := read(); return s.Control.Connected && len(s.Peers) == 1 })
	start := time.Now()
	deadline := time.Now().Add(22 * time.Second)
	var expired PublicStatus
	for time.Now().Before(deadline) {
		s := read()
		if gets.Load() >= 4 && beats.Load() >= 3 && len(s.Peers) == 0 && s.Control.Connected && s.Mode == "transport-test" && s.StatusError == "" {
			expired = s
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	if expired.UpdatedAt == 0 {
		t.Fatalf("expiry not observed: gets=%d beats=%d status=%+v", gets.Load(), beats.Load(), read())
	}
	t.Logf("expired after %.2fs: heartbeat=%d config_requests=%d connected=%v peers=%d tun=%v status_error=%q",
		time.Since(start).Seconds(), beats.Load(), gets.Load(), expired.Control.Connected, len(expired.Peers), expired.TUN.Ready, expired.StatusError)
	recovering.Store(true)
	waitFor(t, func() bool {
		s := read()
		return s.Control.Connected && len(s.Peers) == 1 && s.Peers[0].Path == "probing"
	})
	restored := read()
	t.Logf("recovered: connected=%v peers=%d path=%s", restored.Control.Connected, len(restored.Peers), restored.Peers[0].Path)
}
