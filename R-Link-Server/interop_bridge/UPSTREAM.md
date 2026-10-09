# R-SDK interop v1.0.0 source candidate

Canonical file: `schema.json`, Draft 2020-12, ID `urn:r-sdk:interop:1.0.0`.
`build.py --check` verifies package-local copies and the common corpus. This
candidate has not yet passed all helper/packaging/MSRV checks or parent review.
Do not treat schema acceptance as authentication, approval or authorization.

Consumer entries:

- `@r-sdk/interop`: `packages/interop/src/index.mjs` and `index.d.mts`; Ajv 2020-12.
- `r-interop`: path dependency `crates/r-interop`; `Contract::new`, `parse`,
  `validate`, binding/response/digest/replay helpers, `ClientSession`.
- `r-sdk-interop`: `packages/interop-python`; import `r_sdk_interop`; Python 3.11+,
  `jsonschema==4.26.0`. For source use, add its `src` directory to `PYTHONPATH`.

Every envelope contains schemaVersion=`1.0.0`, kind, requestId, correlationId,
generation and body. Responses echo the IDs and application-owned generation.
Strict JSON parsing rejects duplicate decoded keys, unknown fields, oversized
payloads, unsafe/noninteger numbers and unpaired Unicode surrogates. Limits:
64 KiB, 32 nesting levels, 4096 nodes. Native parser output alone is insufficient.

The first slice provides negotiate.request/response, identity.mapping,
capability.snapshot, approval.snapshot, service.descriptor, agent.request/result,
app.request/result, agent.cancel and bounded problem errors. Exact supported
operations/arguments/output projections are in the schema and fixtures:

- R-Auth identity.resolve, profile.read/update, sessions.list/revoke.
- R-Box resources.list and R-Vault items.list (IDs only).
- R-Link devices.list, tunnels.inspect and migrations.preflight.
- R-OS apps.list and R-Plugin plugins.list, preserving their own appId.

Agent requests accept only reads. The two account writes are app.request only,
require capabilityRef plus expectedResourceRevision, and clients deny them by
default. An opt-in client switch permits sending a request; native ownership,
If-Match, CSRF/bearer policy and current service authorization remain mandatory.
R-Auth session revocation affects only its own sessions, not global IdP/app logout.

R-msg Harness admission changes state and may call a model. It is advertised as
r-msg.harness.run, execute/external_effect/disabled/approval-required, with
NO_ADAPTER for runtime admission. There is no executable Harness request template.
The first msg bridge may call r-vault.items.list through its existing native
gateway. Vault get/create/trash/restore retain their native read/write and per-call
Strict semantics and have no new implicit public template.

Identity mapping matches only an existing exact issuer/sub pair and named app
instance; pairwise-sub mismatch is NOT_LINKED. Never merge by email or sub alone.
Resource-binding helpers operate only on claims already cryptographically
verified as an access token by the resource server, checking issuer/audience/scope/
expiry. Box tokens are not automatically valid in Auth. All credentials stay in
an app-owned injected transport, outside these JSON messages.

Capability/approval helpers check structural bindings only. The service must
freshly resolve issuer trust, reference existence, authenticated actor, ACL,
authorized approver, expiry and revocation for every invocation, replay and
cancellation. Never use caller-supplied snapshots as evidence. Approval binds
request identity, digest, capability, target and resource revision. Python
guard_read requires app-owned authorization callbacks before and after awaiting
the handler. Vault native credential/consent/epoch/Strict prompts remain final;
use uniformly opaque DENIED for hidden/missing/locked/stale/revoked/password errors.

Requests have timeoutMs=1..30000. TIMEOUT is uncertain delivery/completion,
not confirmed cancellation; no client auto-retry exists. Read current state.
Cancel has its own requestId, same target and original runId; the service freshly
checks the original run owner. cancel_requested is admitted soft cancellation;
only target-confirmed cancelled is final. After uncertain effects report
outcome_unknown/OUTCOME_UNKNOWN, never rollback or interrupted-write success.
Late previous-generation responses fail STALE_GENERATION. Generation is owned by
the app/transport and rotates after reconfiguration; caller claims are not trust.
Durable deduplication belongs to the app and is scoped to authenticated caller/
tenant, app instance, target and requestId. Same input replays; changed input
conflicts; authority must be rechecked before cached output is returned.

Digest canonicalization is restricted to ASCII keys and safe integers (not general
RFC 8785): sort object keys, preserve arrays and Unicode scalar strings without
normalization, emit JSON without whitespace, normalize integer representations.
Set only body.approvalRef to null. SHA-256 covers UTF-8 `r-sdk-interop-request/v1`,
one NUL byte, then canonical JSON. Digest equality grants no authority.

Migration is opt-in and additive. Existing auth-node, account-web, discovery API,
R-msg Harness v1 and experimental simulationOnly v0.1 stay independent. New app
adapters/allowlists remain default-off, preserve legacy routes, and must not
auto-enable model/execution or share sessions. Incompatible contract extensions
require a new schema version and exact negotiation. Synthetic fixture parity is
distinct from actual product/device interoperability.

References: [JSON Schema 2020-12](https://json-schema.org/draft/2020-12/json-schema-core),
[OIDC identity stability](https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability),
[RFC 9457 problem fields](https://www.rfc-editor.org/rfc/rfc9457.html).
