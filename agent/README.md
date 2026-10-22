# R-Link native fabric agent

This agent owns enrollment, candidate discovery, route measurement, recovery,
and relay selection. It uses the official WireGuard userspace library for the
encrypted packet protocol and platform TUN adapters. It does not use NetBird's
client, discovery service, management service, or relay.

## Build and verify

```sh
go mod download
go test ./...
go build -trimpath -o rlink-agent ./cmd/rlink-agent
```

Builds need Go 1.25 or later. Dependencies are pinned in `go.mod`/`go.sum`.
Windows builds need the official, signed Wintun DLL installed beside the
executable. macOS uses utun; Linux needs `/dev/net/tun` and the iproute2 tools.

## Enroll and run

An administrator creates a one-time enrollment token in the R-Link fabric
administration page. Read that token from stdin or a protected file; never
place it in command-line arguments or shell history.

```sh
rlink-agent enroll --server https://175.178.16.90/r-link --name mac-air --token-stdin
rlink-agent run --udp-port 51822
rlink-agent status --json
```

The default data and hole-punch port is UDP 51822. The service needs
administrator/root access to create its own adapter and
route. It only installs an assigned private virtual subnet route. It does not
change global DNS, default routes, existing mesh clients, or LAN routing.
Installers must own the executable and state directory with protected ACLs.
The Windows SCM service name is `RLinkFabric`; macOS/Linux can invoke `run`
through launchd/systemd.

Cold OS adapter/address/route setup has a separate 60-second command deadline;
the HTTPS control deadline remains 8 seconds. After slow adapter setup, the
agent refreshes authorization before applying WireGuard peers. Early startup
failure writes only `status_error: startup_failed` to public status and a
separate administrator-only `startup-error.json` containing the startup stage,
fixed detail code, command basename/exit status/deadline, and bounded, redacted
system errors. Windows also records the safe stage/code as Application event
1001 under source `RLinkFabric`. No credential or raw command error is included
in the public status. Existing enrollment identity is preserved on retry.

State locations are fixed: `%ProgramData%\R-Link\Agent` on Windows and
`/var/lib/r-link-agent` on macOS/Linux. `config.json` contains the local
WireGuard private key and machine token (0600/System+Administrators only).
Neither secret is returned by `status --json`; that command only reads the
separate atomically written public `status.json` file (0644 on Unix).

## Data paths and evidence

The same UDP socket sends STUN binding requests and authenticated peer
probes, allowing peers to try LAN candidates and external NAT mappings.
LAN collection rejects known mesh/TUN/bridge interfaces, interfaces without
link-layer addresses, point-to-point adapters, CGNAT and benchmark ranges,
and this agent's own virtual subnet. The same range checks cover signaled
candidates and learned UDP sources, so an old NetBird address cannot become
a native direct path. Public status records candidate origins separately as
`lan`, `stun`, or `advertised`; the REST candidate contract remains IP/port.
`stun-server --listen :51821` runs R-Link's bounded RFC 5389 binding service.
STUN success is a candidate observation and does not prove a working VPN.

Servers with a provider-managed 1:1 NAT can explicitly advertise their own
public mapping, for example `run --udp-port 51822 --public-endpoint
175.178.16.90:51822`. This option accepts only a public IPv4 endpoint and is
empty by default. The agent never derives a PC's public address from its
control URL. Operators must make the advertised UDP port reachable.

Authenticated probe replies measure candidate RTT. The agent selects the
smallest RTT among live direct and relay paths, with a 20%/2 ms switching
margin to prevent oscillation. Paths expire after 12 seconds without a
confirmed probe response. A failed/expired direct path automatically uses
the HTTPS WebSocket relay, and probes continue looking for a shorter path.
UDP source addresses are learned only after pair-secret HMAC verification.
WireGuard encrypts and authenticates the IP packet from endpoint to endpoint;
the relay only forwards opaque authenticated envelopes.

The configuration's authorization TTL is at most 45 seconds. Missing refresh
removes all peers and pair secrets and blocks transport. Heartbeats alone do
not extend peer authorization. The relay identity comes from the authenticated
socket; the agent compares its outer source UUID with the inner source UUID.

Public status distinguishes control connectivity, TUN readiness, measured
direct/relay path, and actual WireGuard handshake/counters. An ordinary UDP
probe does not set `last_handshake`. Final deployment validation must also
exercise a business endpoint (such as virtual-IP SSH) over the tunnel.
`run --no-tun` is a transport-only diagnostic, writes `mode: transport-test`,
and cannot be reported as VPN enrollment or successful TUN deployment.

The integration test uses two actual WireGuard devices with in-memory test
TUNs. It checks decrypted IPv4 payload delivery over authenticated direct UDP,
then over an actual WebSocket relay after forcing direct-path expiration,
and asserts real WireGuard handshake/counter evidence. It does not claim
that a privileged OS TUN has been installed.
