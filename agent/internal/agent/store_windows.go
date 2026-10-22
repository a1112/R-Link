//go:build windows

package agent

import (
	"os"
	"os/exec"
	"path/filepath"

	"golang.org/x/sys/windows"
)

func DefaultDir() string {
	path, e := windows.KnownFolderPath(windows.FOLDERID_ProgramData, 0)
	if e != nil {
		return `C:\ProgramData\R-Link\Agent`
	}
	return filepath.Join(path, "R-Link", "Agent")
}
func secureFile(path string, mode os.FileMode) error {
	if mode.Perm() != 0600 {
		return nil
	}
	cmd := exec.Command(filepath.Join(os.Getenv("SystemRoot"), "System32", "icacls.exe"), path, "/inheritance:r", "/grant:r", "*S-1-5-18:F", "*S-1-5-32-544:F")
	return cmd.Run()
}
