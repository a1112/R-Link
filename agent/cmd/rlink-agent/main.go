package main

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/a1112/R-Link/agent/internal/agent"
)

func main() {
	if e := dispatch(); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
func run(parent context.Context) error {
	if len(os.Args) < 2 {
		return errors.New("usage: rlink-agent enroll|run|status|stun-server")
	}
	// This branch deliberately does not load config.json, machine tokens, or
	// private keys. Its only input is the fixed public status projection.
	if os.Args[1] == "status" {
		if len(os.Args) != 3 || os.Args[2] != "--json" {
			return errors.New("usage: rlink-agent status --json")
		}
		s, e := agent.ReadPublicStatus()
		if e != nil {
			s.SchemaVersion = 1
			s.Provider = "rlink-fabric"
			s.StatusError = e.Error()
		}
		_ = json.NewEncoder(os.Stdout).Encode(s)
		return e
	}
	ctx, cancel := signal.NotifyContext(parent, os.Interrupt, syscall.SIGTERM)
	defer cancel()
	f := flag.NewFlagSet(os.Args[1], flag.ContinueOnError)
	switch os.Args[1] {
	case "enroll":
		server := f.String("server", "", "HTTPS control base URL")
		name := f.String("name", "", "device name")
		tokenStdin := f.Bool("token-stdin", false, "read enrollment token from stdin")
		tokenFile := f.String("token-file", "", "read token from a private enrollment file")
		config := f.String("config", filepath.Join(agent.DefaultDir(), "config.json"), "private service config path")
		if e := f.Parse(os.Args[2:]); e != nil {
			return e
		}
		if f.NArg() != 0 || (*tokenStdin) == (*tokenFile != "") {
			return errors.New("select exactly one enrollment token source")
		}
		if _, e := os.Stat(*config); e == nil {
			return errors.New("already enrolled; existing identity preserved")
		}
		var source io.Reader = os.Stdin
		var file *os.File
		if *tokenFile != "" {
			var e error
			file, e = os.Open(*tokenFile)
			if e != nil {
				return errors.New("cannot open enrollment file")
			}
			defer file.Close()
			source = file
		}
		scanner := bufio.NewScanner(io.LimitReader(source, 1025))
		if !scanner.Scan() {
			return errors.New("missing enrollment token")
		}
		token := strings.TrimSpace(scanner.Text())
		i, e := agent.Enroll(ctx, *server, *name, token)
		token = ""
		if e != nil {
			return e
		}
		if e = agent.SaveIdentity(*config, i); e != nil {
			return errors.New("cannot persist private agent identity")
		}
		fmt.Println("Enrollment saved. Start the privileged agent service to create the virtual network interface.")
		return nil
	case "run":
		config := f.String("config", filepath.Join(agent.DefaultDir(), "config.json"), "private service config path")
		noTUN := f.Bool("no-tun", false, "transport test only; does not enroll a VPN interface")
		port := f.Uint("udp-port", 51822, "UDP data and hole-punch port")
		publicEndpoint := f.String("public-endpoint", "", "explicit operator-configured public IPv4:port advertisement")
		if e := f.Parse(os.Args[2:]); e != nil {
			return e
		}
		if *port > 65535 || f.NArg() != 0 {
			return errors.New("invalid UDP port or arguments")
		}
		return agent.Run(ctx, *config, *noTUN, uint16(*port), *publicEndpoint)
	case "stun-server":
		listen := f.String("listen", ":51821", "UDP binding address")
		if e := f.Parse(os.Args[2:]); e != nil {
			return e
		}
		return agent.ServeSTUN(ctx, *listen)
	default:
		return errors.New("unknown agent command")
	}
}
