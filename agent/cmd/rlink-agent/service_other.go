//go:build !windows

package main

import "context"

func dispatch() error { return run(context.Background()) }
