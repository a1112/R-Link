# Opt-in R-SDK read boundary candidate

This local stage consumes only R-SDK commit
`d321b6ed427472533f5e1a26a75551f69d0726ea`. It supersedes
`cc9fed2027c81a43e69b74d923b7fd13cbdf6d81` with a Node-only absolute delivery
deadline repair. The vendored Python implementation, schema and upstream notes
are byte-identical at both commits. This repository has no tracked Node interop
consumer; the previous native regression evidence remains applicable.
Candidate 3 replaces the rejected first draft and reports repairs to the reviewed
parser, client-generation, mutable-request, output-binding and deadline defects.
Fresh independent review remains pending. Do not release or enable it as a
production read integration. The unchanged migration note is included as
`interop_bridge/MIGRATION.md`; all wire fields/operations remain unchanged.

`R-Link-Server/interop_bridge/SOURCE.json` records every upstream file hash.
Schema SHA-256 is
`b3cb10497f9af87ff23b303098b540ab2ec9d21b4beb8b724458d5d7405e7000`.
R-SDK owns all wire fields and operation templates. This repository owns native
authentication, configured instance identity, inventory/trust and read lifecycle.

`R_LINK_INTEROP_READ_ENABLED=1` at application import opts into
`POST /api/interop/v1/messages` and `GET /api/interop/v1/descriptor`. Defaults
mount no routes. Explicit `R_LINK_INTEROP_INSTANCE_ID`, `_DEVICE_ID`,
`_GENERATION` (positive safe integer) and `_STATE_DIR` are required. Instance or
state-directory changes require restart and an advanced native generation.
This source creates no credentials, trust enrollment, network configuration,
listener, model admission or executable capability.

## Device discovery is blocked by source/schema fidelity

The native `api.devices.list_devices` registry contains device metadata,
connection state and links to the existing device/trust owners. It does not
establish remote R-SDK app instances, service IDs or supported protocol versions.
The candidate `r-link.devices.list` output requires `ServiceDescriptor[]` with
these facts. Using this server's instance ID for each remote device, marking an
SSH endpoint as an SDK endpoint, or labelling arbitrary inventory rows as SDK
services would misrepresent discovery even with `trust=unverified`.

The authenticated **local** service descriptor and negotiation consequently
advertise `r-link.devices.list` as `disabled`, with no remote endpoints and no
verified trust claim. Direct device queries return `NO_ADAPTER`; they do not
invent an empty device list or query/probe/connect to devices. The SDK owner must
approve an inventory-specific projection or a trustworthy discovery source.
R-OS/R-Plugin registry ID reads can use their existing ID-output schemas in the
separate R repository. No consumer-local operation or schema is introduced here.

## Native authority and read lifecycle

Existing `authenticate` retains API/session authority: OIDC browser/desktop
context, CSRF/origin rules, service-key isolation and local access policy. At
least its native viewer role is required. The original principal/session is
freshly checked; descriptors and negotiation confer no device/API permission.
The device and fabric owners continue to own device trust. No credential stores
or session namespaces are combined.

Caller capability/approval references return `DENIED`: this slice has no trusted
reference resolver. Non-null collection revision claims return
`REVISION_CONFLICT`. Exact native instance/device/resource binding is required.
Tunnels, migration preflight, status, SSH/probe/install, plugin execution and model
calls have no adapter. Existing endpoints and disabled capabilities stay intact.

The common app-owned read boundary is included for future owner-approved reads
and matches the R repository's implementation. It calls the SDK parser/guard,
seals a private request, supplies recursively immutable callback views, and checks
request/authority/generation after awaits. A separate supervisor bounds waiting
even if handlers suppress cancellation. Late output is discarded; draining reads
retain one of eight slots. Cancellation is soft admission until actual native
termination, independently of SDK wrapper completion. A private bounded journal
deduplicates within the authenticated actor/instance/request namespace; cached
responses require fresh native authorization. No journal entry is dispatched for
the blocked device operation. Independent SDK review remains a release prerequisite, regardless of these
application guards.

## Local verification

ASGI tests use disposable native OIDC viewer sessions and SQLite inventory to
verify authenticated local descriptor/negotiation, disabled capability admission,
`NO_ADAPTER` without fabricated output or backend invocation, forged-grant and
execute/target denial, native session revocation, epoch/enablement changes and
exact vendor hashes. Native multiuser/local-auth regression tests also run.
The common lifecycle counterexamples run through actual R-OS/R-Plugin registry
handlers in the separate R checkout. R-Link device-list interoperability is
explicitly unverified and blocked.

No test contacts a device, IdP, SSH host, model or network control plane; no
production listener is started.
