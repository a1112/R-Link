package agent

import (
	"encoding/hex"
	"errors"
	"net/netip"
	"path/filepath"
	"strings"
	"time"
)

// Public status carries only startup_failed. Fixed detail codes and underlying
// system-command errors belong to the separate administrator-only diagnostic.
type startupFailure struct {
	Code  string
	Cause error
}

func (e *startupFailure) Error() string          { return e.Code }
func (e *startupFailure) Unwrap() error          { return e.Cause }
func failStartup(code string, cause error) error { return &startupFailure{Code: code, Cause: cause} }

type startupDiagnostic struct {
	At                    int64  `json:"at"`
	Stage                 string `json:"stage"`
	Code                  string `json:"code"`
	Detail                string `json:"detail"`
	Command               string `json:"command,omitempty"`
	CommandExitCode       *int   `json:"command_exit_code,omitempty"`
	CommandTimeoutSeconds int    `json:"command_timeout_seconds,omitempty"`
}

func recordStartupFailure(configPath string, i Identity, stage string, cause error, noTUN bool, port uint16) error {
	code := "startup_failed"
	var failure *startupFailure
	if errors.As(cause, &failure) {
		code = failure.Code
	}
	detail := cause.Error()
	if failure != nil && failure.Cause != nil {
		detail = failure.Cause.Error()
	}
	secrets := []string{i.PrivateKey, i.DeviceToken}
	if key, e := decodeKey(i.PrivateKey); e == nil {
		secrets = append(secrets, hex.EncodeToString(key[:]))
	}
	for _, secret := range secrets {
		if secret != "" {
			detail = strings.ReplaceAll(detail, secret, "[redacted]")
		}
	}
	if len(detail) > 8192 {
		detail = detail[:8192]
	}
	d := startupDiagnostic{At: time.Now().Unix(), Stage: stage, Code: code, Detail: detail}
	var commandError *platformCommandError
	if errors.As(cause, &commandError) {
		exit := commandError.ExitCode
		d.Command = commandError.Command
		d.CommandExitCode = &exit
		d.CommandTimeoutSeconds = int(commandError.Timeout / time.Second)
	}
	dir := filepath.Dir(configPath)
	privateError := writeAtomic(filepath.Join(dir, "startup-error.json"), d, 0600)
	publicID := i.PeerID
	if _, e := ParseID(publicID); e != nil {
		publicID = ""
	}
	publicURL := i.ControlURL
	if _, e := ValidateControlURL(publicURL); e != nil {
		publicURL = ""
	}
	publicName := i.Name
	publicIP := i.VirtualIP
	if _, e := netip.ParseAddr(publicIP); e != nil {
		publicIP = ""
	}
	for _, secret := range secrets {
		if secret != "" {
			publicURL = strings.ReplaceAll(publicURL, secret, "[redacted]")
			publicName = strings.ReplaceAll(publicName, secret, "[redacted]")
		}
	}
	s := PublicStatus{SchemaVersion: 1, Provider: "rlink-fabric", DeviceID: publicID, Name: publicName, ControlURL: publicURL, UpdatedAt: d.At, Mode: "vpn", ListenPort: port, StatusError: "startup_failed", Peers: []PeerStatus{}}
	if noTUN {
		s.Mode = "transport-test"
	}
	s.TUN.IP = publicIP
	_ = SavePublicStatus(dir, s)
	return privateError
}
