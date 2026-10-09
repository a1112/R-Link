"""Pinned R-SDK v1 JSON contracts. Validation never grants authority."""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import math
from importlib.resources import files
from typing import Any, Awaitable, Callable

from jsonschema import Draft202012Validator

VERSION = "1.0.0"
MAX_BYTES = 65536
_SCHEMA = json.loads(files(__package__).joinpath("schema.json").read_text())
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)
_WRITES = {"r-auth.profile.update", "r-auth.sessions.revoke"}
_APPS = {op: op.split(".")[0] for op in (
    "r-auth.identity.resolve", "r-auth.profile.read", "r-auth.profile.update", "r-auth.sessions.list",
    "r-auth.sessions.revoke", "r-box.resources.list", "r-vault.items.list", "r-link.devices.list",
    "r-link.tunnels.inspect", "r-link.migrations.preflight", "r-os.apps.list", "r-plugin.plugins.list")}
Json = dict[str, Any]


class ContractError(ValueError):
    """Bounded stable error code, without copying invalid input or exceptions."""

    def __init__(self, code: str = "SCHEMA_INVALID"):
        self.code = code
        super().__init__(code)


def _fail(code: str = "SCHEMA_INVALID") -> None:
    raise ContractError(code)


def _admit(value: Any) -> None:
    nodes = 0

    def walk(item: Any, depth: int) -> None:
        nonlocal nodes
        nodes += 1
        if nodes > 4096 or depth > 32:
            _fail()
        if item is None or type(item) is bool:
            return
        if type(item) in (int, float):
            if not math.isfinite(item) or int(item) != item or abs(item) > 9007199254740991:
                _fail()
            return
        if type(item) is str:
            if any(0xD800 <= ord(c) <= 0xDFFF for c in item):
                _fail()
            return
        if type(item) is list:
            for child in item:
                walk(child, depth + 1)
            return
        if type(item) is not dict:
            _fail()
        for key, child in item.items():
            if not isinstance(key, str) or not key.isascii() or not key or not key[0].isalpha() or not key.isalnum():
                _fail()
            walk(child, depth + 1)

    walk(value, 0)
    if len(_canonical(value).encode()) > MAX_BYTES:
        _fail()


def _canonical(value: Any) -> str:
    if type(value) in (int, float) and type(value) is not bool:
        return str(int(value))
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + _canonical(value[k]) for k in sorted(value)) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_canonical(child) for child in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _def(name: str, value: Any) -> None:
    _admit(value)
    if not _VALIDATOR.evolve(schema={"$ref": "#/$defs/" + name}).is_valid(value):
        _fail()


def _unique_capabilities(items: list[Json]) -> None:
    if len({item["id"] for item in items}) != len(items):
        _fail("BINDING_MISMATCH")


def _problem(problem: Json) -> None:
    if problem["type"] != "urn:r-sdk:problem:" + problem["code"]:
        _fail("BINDING_MISMATCH")


def _semantic(value: Json) -> None:
    b, kind = value["body"], value["kind"]
    if kind == "negotiate.request":
        _unique_capabilities(b["requiredCapabilities"])
    if kind == "negotiate.response":
        _unique_capabilities(b["capabilities"])
    if kind == "service.descriptor":
        _unique_capabilities(b["capabilities"])
        for e in b["endpoints"]:
            # fe80::/10 requires the observed interface's scope, as in discovery-core.
            if len(e["host"]) > 4 and e["host"][:2].lower() == "fe" and e["host"][2].lower() in "89ab" and e["host"][4] == ":" and not e.get("scopeId"):
                _fail("BINDING_MISMATCH")
    if kind in ("capability.snapshot", "approval.snapshot"):
        if b["expiresAtMs"] <= b["issuedAtMs"]:
            _fail("BINDING_MISMATCH")
        if kind == "capability.snapshot" and any(b["audience"][k] != b["target"][k] for k in ("appId", "appInstanceId")):
            _fail("BINDING_MISMATCH")
    if kind in ("agent.request", "app.request"):
        op, args, target = b["operation"], b["arguments"], b["target"]
        if _APPS[op] != target["appId"]:
            _fail("BINDING_MISMATCH")
        if op == "r-link.tunnels.inspect" and args["tunnelId"] != target["resourceId"]:
            _fail("BINDING_MISMATCH")
        if op == "r-link.migrations.preflight":
            src, dst = args["source"], args["destination"]
            if not src.get("deviceId") or not dst.get("deviceId") or src["deviceId"] == dst["deviceId"] or src != target or src["appId"] != "r-link" or dst["appId"] != "r-link":
                _fail("BINDING_MISMATCH")
        if op.startswith("r-auth.profile.") and target["resourceId"] != "profile":
            _fail("BINDING_MISMATCH")
        if op == "r-auth.sessions.revoke" and target["resourceId"] != args["sessionId"]:
            _fail("BINDING_MISMATCH")
    if kind in ("agent.result", "app.result"):
        if _APPS[b["operation"]] != b["target"]["appId"]:
            _fail("BINDING_MISMATCH")
        state, output, problem = b["state"], b["output"], b["problem"]
        if state == "completed":
            if output is None or problem is not None:
                _fail("BINDING_MISMATCH")
        elif state in ("failed", "outcome_unknown"):
            if output is not None or problem is None:
                _fail("BINDING_MISMATCH")
        elif output is not None or problem is not None:
            _fail("BINDING_MISMATCH")
        if state == "outcome_unknown" and problem["code"] != "OUTCOME_UNKNOWN":
            _fail("BINDING_MISMATCH")
        if problem:
            _problem(problem)
        if output and "sessions" in output:
            sessions = output["sessions"]
            if len({s["sessionId"] for s in sessions}) != len(sessions) or sum(s["current"] for s in sessions) > 1:
                _fail("BINDING_MISMATCH")
            for s in sessions:
                if s["createdAtMs"] > s["lastSeenAtMs"] or s["lastSeenAtMs"] >= s["expiresAtMs"]:
                    _fail("BINDING_MISMATCH")
        if output and "services" in output:
            for descriptor in output["services"]:
                _semantic({"kind": "service.descriptor", "body": descriptor})
    if kind == "error":
        _problem(b)


def validate(value: Any) -> Json:
    """Validate bounded parsed JSON and service-independent binding invariants."""
    _admit(value)
    if not _VALIDATOR.is_valid(value):
        _fail()
    _semantic(value)
    return value


def parse(text: str) -> Json:
    """Parse strict JSON, rejecting duplicate (including escaped) property names."""
    if type(text) is not str:
        _fail()
    try:
        if len(text.encode()) > MAX_BYTES:
            _fail()

        def pairs(items: list[tuple[str, Any]]) -> Json:
            out = {}
            for key, value in items:
                if key in out:
                    _fail()
                out[key] = value
            return out

        return validate(json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: _fail()))
    except ContractError:
        raise
    except (ValueError, TypeError, RecursionError, UnicodeError):
        _fail()


def map_identity(mapping: Json, identity: Json, audience: Json) -> str:
    """Resolve only an exact authenticated issuer/sub and application instance."""
    _def("IdentityMapping", mapping)
    _def("IdentityRef", identity)
    _def("Audience", audience)
    if mapping["identity"] != identity or any(mapping["app"][k] != audience[k] for k in ("appId", "appInstanceId")):
        _fail("NOT_LINKED")
    return mapping["app"]["localUserId"]


def check_resource_binding(context: Json, policy: Json) -> Json:
    """Check verified bearer claims; signature/token-kind validation belongs to the resource server."""
    _admit(context)
    _admit(policy)
    if set(context) != {"identity", "audiences", "scopes", "expiresAtMs"}:
        _fail()
    _def("IdentityRef", context["identity"])
    if type(context["audiences"]) is not list or type(context["scopes"]) is not list or len(context["audiences"]) > 32 or len(context["scopes"]) > 64 or not all(type(v) is str for v in context["audiences"] + context["scopes"]) or type(context["expiresAtMs"]) is not int or type(policy.get("nowMs")) is not int:
        _fail()
    if context["identity"]["issuer"] != policy.get("issuer") or policy.get("audience") not in context["audiences"] or policy.get("scope") not in context["scopes"]:
        _fail("FORBIDDEN")
    if context["expiresAtMs"] <= policy["nowMs"]:
        _fail("REFERENCE_EXPIRED")
    return context["identity"]


def check_capability_binding(request: Json, snapshot: Json, identity: Json, now_ms: int) -> None:
    """Check freshly resolved capability reference wiring, without granting authority."""
    validate(request)
    validate(snapshot)
    _def("IdentityRef", identity)
    if type(now_ms) is not int or now_ms < 0 or request["kind"] not in ("agent.request", "app.request") or snapshot["kind"] != "capability.snapshot":
        _fail()
    b, s = request["body"], snapshot["body"]
    if b["capabilityRef"] != s["reference"] or s["subject"] != identity or b["target"] != s["target"] or b["operation"] != s["capabilityId"] or s["permission"] != ("write" if b["operation"] in _WRITES else "read"):
        _fail("BINDING_MISMATCH")
    if s["state"] == "revoked":
        _fail("REFERENCE_REVOKED")
    if not s["issuedAtMs"] <= now_ms < s["expiresAtMs"]:
        _fail("REFERENCE_EXPIRED")


def request_digest(request: Json) -> str:
    """Restricted integer/ASCII-key canonical digest; never a signature or grant."""
    validate(request)
    if request["kind"] not in ("agent.request", "app.request"):
        _fail()
    projection = copy.deepcopy(request)
    projection["body"]["approvalRef"] = None
    return "sha256:" + hashlib.sha256(b"r-sdk-interop-request/v1\0" + _canonical(projection).encode()).hexdigest()


def check_approval_binding(request: Json, snapshot: Json, now_ms: int) -> None:
    """Check a trusted resolver's exact request/target/revision and fresh revocation snapshot."""
    validate(request)
    validate(snapshot)
    if snapshot["kind"] != "approval.snapshot" or type(now_ms) is not int or now_ms < 0:
        _fail()
    b, s = request["body"], snapshot["body"]
    if b["approvalRef"] != s["reference"] or request["requestId"] != s["requestId"] or b["capabilityRef"] != s["capabilityRef"] or b["operation"] != s["capabilityId"] or b["target"] != s["target"] or b["expectedResourceRevision"] != s["resourceRevision"] or s["permission"] != ("write" if b["operation"] in _WRITES else "read") or request_digest(request) != s["requestDigest"]:
        _fail("BINDING_MISMATCH")
    if s["state"] == "revoked":
        _fail("REFERENCE_REVOKED")
    if not s["issuedAtMs"] <= now_ms < s["expiresAtMs"]:
        _fail("REFERENCE_EXPIRED")


def check_response(request: Json, response: Json) -> Json:
    """Reject mismatched correlation, operation, target, cancellation run or transport generation."""
    validate(request)
    validate(response)
    if request["generation"] != response["generation"]:
        _fail("STALE_GENERATION")
    if any(request[k] != response[k] for k in ("requestId", "correlationId")):
        _fail("BINDING_MISMATCH")
    if response["kind"] == "error":
        return response
    expected = {"negotiate.request": "negotiate.response", "agent.request": "agent.result", "app.request": "app.result", "agent.cancel": "agent.result"}.get(request["kind"])
    if not expected or response["kind"] != expected:
        _fail("BINDING_MISMATCH")
    a, b = request["body"], response["body"]
    if "target" in a and a["target"] != b["target"] or "operation" in a and a["operation"] != b["operation"]:
        _fail("BINDING_MISMATCH")
    if request["kind"] == "agent.cancel" and a["runId"] != b["runId"]:
        _fail("BINDING_MISMATCH")
    if request["kind"] == "negotiate.request":
        if b["selectedVersion"] not in a["versions"]:
            _fail("UNSUPPORTED_VERSION")
        for required in a["requiredCapabilities"]:
            if not any(c["id"] == required["id"] and c["version"] == required["version"] and c["availability"] == "enabled" for c in b["capabilities"]):
                _fail("CAPABILITY_UNAVAILABLE")
    return response


def compare_request_reuse(previous: Json, next_request: Json) -> str:
    """Use inside a service-owned authenticated caller/target namespace, never as an auth cache."""
    validate(previous)
    validate(next_request)
    if previous["kind"] not in ("app.request", "agent.request", "agent.cancel") or previous["kind"] != next_request["kind"]:
        _fail()
    if previous["generation"] != next_request["generation"]:
        _fail("STALE_GENERATION")
    if previous["requestId"] != next_request["requestId"]:
        return "new"
    return "replay" if previous == next_request else "conflict"


class Client:
    """Injected application-owned async transport, no credentials, retries or auto-execution."""

    def __init__(self, exchange: Callable[[str], Awaitable[str]], *, allow_application_writes: bool = False):
        if not callable(exchange) or type(allow_application_writes) is not bool:
            _fail()
        self.exchange = exchange
        self.allow_application_writes = allow_application_writes
        self.negotiated: Json | None = None

    async def _exchange(self, request: Json) -> Json:
        try:
            text = await asyncio.wait_for(self.exchange(json.dumps(request, ensure_ascii=False)), request["body"].get("timeoutMs", 5000) / 1000)
            return check_response(request, parse(text))
        except TimeoutError:
            _fail("TIMEOUT")

    async def negotiate(self, request: Json) -> Json:
        self.negotiated = None
        validate(request)
        if request["kind"] != "negotiate.request":
            _fail()
        response = await self._exchange(request)
        if response["kind"] == "error":
            _fail(response["body"]["code"])
        self.negotiated = {**copy.deepcopy(response["body"]), "generation": response["generation"]}
        return response

    async def call(self, request: Json) -> Json:
        validate(request)
        if self.negotiated is None:
            _fail("UNSUPPORTED_VERSION")
        if request["generation"] != self.negotiated["generation"]:
            _fail("STALE_GENERATION")
        if request["kind"] not in ("app.request", "agent.request", "agent.cancel"):
            _fail()
        if request["kind"] != "agent.cancel":
            op = request["body"]["operation"]
            if op in _WRITES and not self.allow_application_writes:
                _fail("EXECUTION_DISABLED")
            if not any(c["id"] == op and c["version"] == VERSION and c["permission"] == ("write" if op in _WRITES else "read") and c["availability"] == "enabled" for c in self.negotiated["capabilities"]):
                _fail("CAPABILITY_UNAVAILABLE")
        return await self._exchange(request)


async def guard_read(request: Json, *, authorize: Callable[[Json], Awaitable[bool]],
                     handler: Callable[[Json], Awaitable[Json]], generation: Callable[[], int]) -> Json:
    """Recheck app-owned authority before and after an awaited, explicitly allowlisted read."""
    validate(request)
    if request["kind"] not in ("agent.request", "app.request") or request["body"]["mode"] != "read_only":
        _fail("EXECUTION_DISABLED")
    if not all(callable(c) for c in (authorize, handler, generation)):
        _fail()

    async def check() -> None:
        if request["generation"] != generation():
            _fail("STALE_GENERATION")
        if await authorize(request) is not True:
            _fail("FORBIDDEN")

    async def dispatch() -> Json:
        await check()
        response = await handler(request)
        await check()
        return check_response(request, response)

    try:
        return await asyncio.wait_for(dispatch(), request["body"]["timeoutMs"] / 1000)
    except TimeoutError:
        _fail("TIMEOUT")
