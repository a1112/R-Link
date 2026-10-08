package agent

import (
	"context"
	"fmt"
	"os/exec"
	"path/filepath"
	"sync"
	"time"
)

const interfaceCommandTimeout = 60 * time.Second

type platformCommandError struct {
	Command  string
	Timeout  time.Duration
	TimedOut bool
	ExitCode int
	Output   string
	Cause    error
}

func (e *platformCommandError) Error() string {
	if e.TimedOut {
		return fmt.Sprintf("virtual interface command timed out after %s; %s", e.Timeout, e.Output)
	}
	return fmt.Sprintf("virtual interface command exited %d; %s", e.ExitCode, e.Output)
}
func (e *platformCommandError) Unwrap() error { return e.Cause }

type diagnosticBuffer struct {
	mu   sync.Mutex
	data []byte
}

func (b *diagnosticBuffer) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	n := len(p)
	remaining := 8192 - len(b.data)
	if remaining > 0 {
		if len(p) > remaining {
			p = p[:remaining]
		}
		b.data = append(b.data, p...)
	}
	return n, nil
}
func command(path string, args ...string) error {
	return commandWithTimeout(interfaceCommandTimeout, path, args...)
}
func commandWithTimeout(timeout time.Duration, path string, args ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, path, args...)
	cmd.WaitDelay = 2 * time.Second
	output := new(diagnosticBuffer)
	cmd.Stdout = output
	cmd.Stderr = output
	if err := cmd.Run(); err != nil {
		exitCode := -1
		if cmd.ProcessState != nil {
			exitCode = cmd.ProcessState.ExitCode()
		}
		return &platformCommandError{Command: filepath.Base(path), Timeout: timeout, TimedOut: ctx.Err() != nil, ExitCode: exitCode, Output: string(output.data), Cause: err}
	}
	return nil
}
