package agent

import (
	"crypto/ecdh"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"time"
)

func writeAtomic(path string, value any, mode os.FileMode) error {
	dir := filepath.Dir(path)
	if e := os.MkdirAll(dir, 0755); e != nil {
		return e
	}
	data, e := json.MarshalIndent(value, "", "  ")
	if e != nil {
		return e
	}
	file, e := os.CreateTemp(dir, ".rlink-*.tmp")
	if e != nil {
		return e
	}
	name := file.Name()
	defer os.Remove(name)
	if e = file.Chmod(mode); e == nil {
		e = secureFile(name, mode)
	}
	if e == nil {
		_, e = file.Write(data)
	}
	if e == nil {
		e = file.Sync()
	}
	closeErr := file.Close()
	if e != nil {
		return e
	}
	if closeErr != nil {
		return closeErr
	}
	if e = os.Rename(name, path); e != nil {
		return e
	}
	return secureFile(path, mode)
}
func SaveIdentity(path string, i Identity) error { return writeAtomic(path, i, 0600) }
func LoadIdentity(path string) (Identity, error) {
	var i Identity
	data, e := os.ReadFile(path)
	if e != nil {
		return i, e
	}
	if len(data) > 16384 {
		return i, errors.New("identity file too large")
	}
	if e = json.Unmarshal(data, &i); e != nil {
		return i, errors.New("invalid identity file")
	}
	if _, e = ParseID(i.PeerID); e != nil {
		return i, e
	}
	if _, e = ValidateControlURL(i.ControlURL); e != nil {
		return i, e
	}
	private, e := decodeKey(i.PrivateKey)
	if e != nil {
		return i, e
	}
	public, e := decodeKey(i.PublicKey)
	if e != nil {
		return i, e
	}
	k, e := ecdh.X25519().NewPrivateKey(private[:])
	if e != nil || subtle.ConstantTimeCompare(k.PublicKey().Bytes(), public[:]) != 1 {
		return i, errors.New("identity key mismatch")
	}
	if len(i.DeviceToken) < 32 || len(i.DeviceToken) > 1024 {
		return i, errors.New("invalid device token")
	}
	return i, nil
}
func SavePublicStatus(dir string, s PublicStatus) error {
	return writeAtomic(filepath.Join(dir, "status.json"), s, 0644)
}
func ReadPublicStatus() (PublicStatus, error) {
	var s PublicStatus
	path := filepath.Join(DefaultDir(), "status.json")
	info, e := os.Lstat(path)
	if e != nil {
		return s, errors.New("not_running")
	}
	if !info.Mode().IsRegular() || info.Size() > 1024*1024 {
		return s, errors.New("invalid_status")
	}
	data, e := os.ReadFile(path)
	if e != nil {
		return s, errors.New("not_running")
	}
	if json.Unmarshal(data, &s) != nil || s.SchemaVersion != 1 || s.Provider != "rlink-fabric" {
		return s, errors.New("invalid_status")
	}
	now := time.Now().Unix()
	if s.StatusError == "startup_failed" {
		s.Control.Connected = false
		s.TUN.Ready = false
		return s, errors.New("startup_failed")
	}
	if s.UpdatedAt < now-45 || s.UpdatedAt > now+5 {
		s.Control.Connected = false
		s.TUN.Ready = false
		for k := range s.Peers {
			s.Peers[k].Path = "offline"
		}
		s.StatusError = "stale"
		return s, errors.New("stale")
	}
	return s, nil
}
