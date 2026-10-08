//go:build !windows && !linux && !darwin

package agent

import "errors"

func interfaceName() string { return "rlink0" }
func configureInterface(string, string, int) (func(), error) {
	return nil, errors.New("unsupported platform")
}
