//go:build !windows

package agent

import "os"

func DefaultDir() string                             { return "/var/lib/r-link-agent" }
func secureFile(path string, mode os.FileMode) error { return os.Chmod(path, mode) }
