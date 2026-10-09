# Candidate 3 migration from 0e4f261

This replaces the rejected source candidate `0e4f261038a80f5fd8d28f78a323b930e3a29c03`.
Candidate 2 was an uncommitted checkpoint, not a frozen release.
Source packages are Node/Rust `1.0.0-rc.3`, Python `1.0.0rc3`. Wire `schemaVersion`
remains `1.0.0` because these private drafts were never stable releases.
No field, kind, operation ID, import, argument or output projection was added/removed.
The corrected validation rules change the schema hash to
`b3cb10497f9af87ff23b303098b540ab2ec9d21b4beb8b724458d5d7405e7000`.
Pin this source commit and hash together; do not mix prior draft validators.

Consumer changes:

- Feed serialized messages through SDK `parse`, before an ordinary JSON parser
  can round raw decimals. Exactly integral values such as `1.0` and `1e0` are
  normalized; `1.00000000000000001` and `9007199254740990.1` are rejected.
  Already-parsed numbers cannot reveal lost precision. All numeric fields must
  be mathematical safe integers within their field limits.
- Issuers use the configured exact ASCII HTTPS URI spelling with RFC 3986 path
  characters; non-ASCII must be percent-encoded. No issuer/sub normalization or
  email join occurs. Patterned IDs/versions/hosts cannot end in line separators.
- Known capability IDs have fixed permission/effect. `r-msg.harness.run` is always
  `execute/external_effect/disabled/required`; it cannot be negotiated as a read.
  It has no executable request shape. Consumer Harness admission must return
  `NO_ADAPTER` without invoking a native executor.
- Tunnel/session IDs and preflight source/destination outputs must agree with the
  original request and target, including opt-in application-write results.
- Starting a negotiation invalidates earlier pending negotiations/calls. Their
  replies cannot restore or deliver an older client epoch.
- Python `guard_read` copies requests before awaiting, gives each callback a
  separate copy, and checks fresh authorization and generation before dispatch
  and output release. Missing/nonboolean/false authorization never dispatches.
- Python deadlines return `TIMEOUT` without waiting for cancellation-resistant
  callbacks. Late output is discarded; late authorization cannot dispatch a
  handler. App-owned coroutine cleanup may continue. Neither timeout nor local
  cancellation confirms native/remote rollback; automatic retry is never added.
- Rust library dependencies now use compatible ranges, retaining the SDK's own
  tested lock without forcing consumer serde/serde_json patch downgrades. Keep
  each consumer's lock and run its complete regression suite; see the crate README.

All original 54 generated corpus cases remain. The byte-identical 65 independent
review inputs now have explicit corrected expectations in all package suites,
alongside lifecycle/deadline regressions. Old review evidence is unchanged.

This is a private source candidate pending fresh independent review and native
consumer integration. Validation/binding does not establish issuer trust, token
kind/signatures, current ACL, consent, approver authorization, reference existence
or revocation. Auth sessions, Vault credentials/epoch/Strict rules and device trust
remain in their applications. Replay/cancellation need current app authorization
and persistent authenticated caller/tenant/instance/run scoping.

No production deployment, real grant/credential, network policy change or real
personal data was used. MSRV/full workspace checks and Python wheel packaging
remain coordinated separately. Synthetic conformance is not product interoperability.
