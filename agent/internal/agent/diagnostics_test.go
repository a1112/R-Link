package agent

import (
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestStartupFailureIsPublicSafeAndPrivateDetailsAreRedacted(t *testing.T) {
	i := testIdentity(t, testID(1), "10.253.199.2")
	i.DeviceToken = "unit-test-machine-token-must-never-be-public"
	private, _ := decodeKey(i.PrivateKey)
	keyHex := hex.EncodeToString(private[:])
	dir := t.TempDir()
	cause := failStartup("route_config_timeout", &platformCommandError{Command: "powershell.exe", Timeout: 60 * time.Second, TimedOut: true, ExitCode: -1, Output: "controlled failure " + i.DeviceToken + " " + i.PrivateKey + " " + keyHex})
	privateError := recordStartupFailure(filepath.Join(dir, "config.json"), i, "interface", cause, false, 51822)
	public, e := os.ReadFile(filepath.Join(dir, "status.json"))
	if e != nil {
		t.Fatal(e)
	}
	for _, secret := range []string{i.DeviceToken, i.PrivateKey, keyHex} {
		if strings.Contains(string(public), secret) {
			t.Fatal("credential leaked into public failure status")
		}
	}
	var s PublicStatus
	if json.Unmarshal(public, &s) != nil || s.StatusError != "startup_failed" || s.Control.Connected || s.TUN.Ready || len(s.Peers) != 0 {
		t.Fatal("public startup failure claims readiness")
	}
	if strings.Contains(string(public), "controlled failure") || strings.Contains(string(public), "route_config_timeout") {
		t.Fatal("raw/private startup detail appeared in public status")
	}
	privatePath := filepath.Join(dir, "startup-error.json")
	raw, e := os.ReadFile(privatePath)
	if e != nil {
		if runtime.GOOS == "windows" && (os.IsPermission(e) || os.IsPermission(privateError)) {
			return
		}
		t.Fatal(e)
	}
	for _, secret := range []string{i.DeviceToken, i.PrivateKey, keyHex} {
		if strings.Contains(string(raw), secret) {
			t.Fatal("credential leaked into private diagnostic")
		}
	}
	var d startupDiagnostic
	if json.Unmarshal(raw, &d) != nil || d.Command != "powershell.exe" || d.Code != "route_config_timeout" || d.CommandTimeoutSeconds != 60 {
		t.Fatal("private diagnostic missing safe operation details")
	}
	if runtime.GOOS != "windows" {
		info, e := os.Stat(privatePath)
		if e != nil || info.Mode().Perm() != 0600 {
			t.Fatal("private diagnostic does not have 0600 permissions")
		}
	}
}

func TestInterfaceCommandRecordsBoundedTimeoutAndExitFailure(t *testing.T) {
	// Execute the test binary as a child process: no shell, administrator
	// privilege, actual adapter or TUN is involved in this timeout regression.
	executable, e := os.Executable()
	if e != nil {
		t.Fatal(e)
	}
	t.Setenv("RLINK_COMMAND_HELPER", "timeout")
	start := time.Now()
	e = commandWithTimeout(150*time.Millisecond, executable, "-test.run=^TestInterfaceCommandHelper$")
	var ce *platformCommandError
	if !errors.As(e, &ce) || !ce.TimedOut || ce.Timeout != 150*time.Millisecond || time.Since(start) > 4*time.Second {
		t.Fatalf("interface command did not preserve bounded timeout: %v", e)
	}
	t.Setenv("RLINK_COMMAND_HELPER", "exit")
	e = commandWithTimeout(5*time.Second, executable, "-test.run=^TestInterfaceCommandHelper$")
	if !errors.As(e, &ce) || ce.ExitCode != 7 || ce.TimedOut || !strings.Contains(ce.Output, "controlled interface error") {
		t.Fatalf("controlled exit failure missing diagnostic: %v", e)
	}
	if interfaceCommandTimeout != 60*time.Second {
		t.Fatal("cold OS interface configuration timeout regressed")
	}
}
func TestInterfaceCommandHelper(t *testing.T) {
	switch os.Getenv("RLINK_COMMAND_HELPER") {
	case "timeout":
		select {
		case <-context.Background().Done():
		case <-time.After(10 * time.Second):
		}
	case "exit":
		_, _ = os.Stderr.WriteString("controlled interface error")
		os.Exit(7)
	}
}
