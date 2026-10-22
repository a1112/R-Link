"""Bounded native read dispatch and an app-owned durable request journal.

All wire validation and response/replay bindings belong to the vendored SDK.
This module owns no credentials, capability grants, plugin or device lifecycle.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from ._vendor.r_sdk_interop import (
    VERSION,
    ContractError,
    check_response,
    compare_request_reuse,
    guard_read,
    parse,
    validate,
)
from .binding import ReadView, check_seal, read_view, seal

Json = dict[str, Any]
Authorize = Callable[[ReadView], Awaitable[bool]]
Recheck = Callable[[ReadView], bool]
Handler = Callable[[ReadView], Awaitable[Json]]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    """Operator-configured native instance identity, separate from credentials."""

    prefix: str
    app_id: str
    operation: str
    resource_id: str
    instance_id: str
    device_id: str
    generation: int
    journal: Path

    @classmethod
    def from_env(
        cls, prefix: str, app_id: str, operation: str, resource_id: str
    ) -> Settings:
        """Require explicit opt-in and instance settings without creating grants."""
        if os.getenv(prefix + "_READ_ENABLED") != "1":
            raise ContractError("EXECUTION_DISABLED")
        try:
            values = [
                os.environ[prefix + suffix]
                for suffix in (
                    "_INSTANCE_ID",
                    "_DEVICE_ID",
                    "_GENERATION",
                    "_STATE_DIR",
                )
            ]
            if not all(values) or not values[2].isascii() or not values[2].isdigit():
                raise ValueError
            generation = int(values[2])
            if not 1 <= generation <= 9007199254740991:
                raise ValueError
        except (KeyError, ValueError):
            raise ContractError("NOT_CONFIGURED") from None
        result = cls(
            prefix,
            app_id,
            operation,
            resource_id,
            values[0],
            values[1],
            generation,
            Path(values[3]) / "interop-reads.sqlite3",
        )
        validate(result.envelope("service.descriptor", result.descriptor()))
        return result

    def current_generation(self) -> int:
        """Read the application-owned epoch on every authority check."""
        value = os.getenv(self.prefix + "_GENERATION", "")
        if (
            not value.isascii()
            or not value.isdigit()
            or not 1 <= int(value) <= 9007199254740991
        ):
            raise ContractError("NOT_CONFIGURED")
        return int(value)

    def enabled(self) -> bool:
        """Reject live identity reconfiguration until restart and renegotiation."""
        return (
            os.getenv(self.prefix + "_READ_ENABLED") == "1"
            and os.getenv(self.prefix + "_INSTANCE_ID") == self.instance_id
            and os.getenv(self.prefix + "_DEVICE_ID") == self.device_id
            and os.getenv(self.prefix + "_STATE_DIR") == str(self.journal.parent)
        )

    def target(self) -> Json:
        """Return this native instance's exact collection binding."""
        return {
            "appId": self.app_id,
            "appInstanceId": self.instance_id,
            "deviceId": self.device_id,
            "resourceId": self.resource_id,
        }

    def capability(self, available: bool = True) -> Json:
        """Advertise only the implemented native read operation."""
        return {
            "id": self.operation,
            "version": VERSION,
            "permission": "read",
            "effect": "read_only",
            "availability": "enabled" if available else "disabled",
            "approval": "none",
        }

    def descriptor(self, available: bool = True) -> Json:
        """Describe the local adapter without asserting discovery trust."""
        return {
            "deviceId": self.device_id,
            "appId": self.app_id,
            "appInstanceId": self.instance_id,
            "serviceId": "interop-read",
            "protocolVersions": [VERSION],
            "capabilities": [self.capability(available)],
            "endpoints": [],
            "trust": "unverified",
        }

    def envelope(self, kind: str, body: Json, request: Json | None = None) -> Json:
        """Bind server-produced output to its request and current native epoch."""
        return {
            "schemaVersion": VERSION,
            "kind": kind,
            "requestId": request["requestId"] if request else str(uuid4()),
            "correlationId": request["correlationId"] if request else str(uuid4()),
            "generation": self.current_generation(),
            "body": body,
        }


def problem(code: str) -> Json:
    """Map bounded codes without exposing payloads or backend exception text."""
    status = {
        "UNAUTHENTICATED": 401,
        "FORBIDDEN": 403,
        "DENIED": 403,
        "UNAVAILABLE": 503,
        "NOT_CONFIGURED": 503,
        "TIMEOUT": 504,
        "INTERNAL": 500,
        "IDEMPOTENCY_CONFLICT": 409,
        "STALE_GENERATION": 409,
        "OUTCOME_UNKNOWN": 409,
    }.get(code, 400)
    return {
        "type": "urn:r-sdk:problem:" + code,
        "title": code,
        "status": status,
        "code": code,
        "retryable": False,
        "nextAction": "read_snapshot"
        if code in {"TIMEOUT", "OUTCOME_UNKNOWN"}
        else "authenticate"
        if code == "UNAUTHENTICATED"
        else "stop",
    }


class ReadService:
    """Dispatch one explicit read through fresh native authorization and SDK guards."""

    def __init__(
        self, settings: Settings, handler: Handler, *, available: bool = True
    ) -> None:
        self.settings = settings
        self.handler = handler
        self.available = available
        self.active: dict[str, asyncio.Task[Json]] = {}
        self.workers: dict[str, asyncio.Task[Json]] = {}
        self.native_pending: dict[str, asyncio.Event] = {}
        self.authorizations: set[asyncio.Task[bool]] = set()
        self.cancel_requested: set[str] = set()
        settings.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.database() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS requests (
                actor TEXT NOT NULL, request_id TEXT NOT NULL, request TEXT NOT NULL,
                run_id TEXT NOT NULL, response TEXT,
                PRIMARY KEY(actor,request_id))""")
        os.chmod(settings.journal, 0o600)

    @contextmanager
    def database(self) -> Iterator[sqlite3.Connection]:
        """Open only this adapter's bounded journal, never another service's store."""
        db = sqlite3.connect(self.settings.journal, timeout=0.1)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def error(self, request: Json, code: str) -> Json:
        """Produce an SDK error bound to the server's current generation."""
        try:
            response = self.settings.envelope("error", problem(code), request)
        except ContractError:
            response = {
                **request,
                "kind": "error",
                "generation": self.settings.generation,
                "body": problem("NOT_CONFIGURED"),
            }
        return validate(response)

    def check_local(self, request: Json, deadline: float | None = None) -> None:
        """Check app-owned state after every authorization/handler await."""
        if request["generation"] != self.settings.current_generation():
            raise ContractError("STALE_GENERATION")
        if not self.settings.enabled():
            raise ContractError("FORBIDDEN")
        if deadline is not None and asyncio.get_running_loop().time() >= deadline:
            raise ContractError("TIMEOUT")

    async def check(
        self,
        request: Json,
        authorize: Authorize,
        deadline: float | None = None,
        *,
        recheck: Recheck,
    ) -> None:
        """Bind native authority to an immutable frame before and after awaiting it."""
        expected = seal(request)
        self.check_local(request, deadline)
        if len(self.authorizations) >= 8:
            raise ContractError("UNAVAILABLE")

        async def lookup() -> bool:
            return await authorize(read_view(request))

        task = asyncio.create_task(lookup())
        self.authorizations.add(task)
        task.add_done_callback(self.authorization_stopped)
        try:
            end = (
                deadline
                if deadline is not None
                else asyncio.get_running_loop().time() + 5
            )
            done, _ = await asyncio.wait(
                {task}, timeout=max(0, end - asyncio.get_running_loop().time())
            )
            if not done:
                task.cancel()
                raise ContractError("TIMEOUT")
            self.check_local(request, end)
            allowed = task.result()
        except asyncio.CancelledError:
            task.cancel()
            raise
        except TypeError:
            raise ContractError("BINDING_MISMATCH") from None
        check_seal(request, expected)
        if allowed is not True:
            raise ContractError("FORBIDDEN")
        self.commit(request, recheck, end)

    def commit(self, request: Json, recheck: Recheck, deadline: float | None = None) -> None:
        """Linearize native authority without yielding, then check the same deadline."""
        expected = seal(request)
        self.check_local(request, deadline)
        allowed = recheck(read_view(request))
        check_seal(request, expected)
        self.check_local(request, deadline)
        if allowed is not True:
            raise ContractError("FORBIDDEN")

    def deliver(
        self, request: Json, response: Json, recheck: Recheck, deadline: float
    ) -> Json:
        """Validate first and commit current native authority at final result release."""
        response = check_response(request, response)
        self.commit(request, recheck, deadline)
        return response

    def authorization_stopped(self, task: asyncio.Task[bool]) -> None:
        """Retain a slot until cancelled authority lookup actually finishes."""
        self.authorizations.discard(task)
        if not task.cancelled():
            task.exception()

    def result(
        self,
        request: Json,
        run_id: str,
        state: str,
        output: Json | None = None,
        code: str | None = None,
    ) -> Json:
        """Project a read lifecycle result into the owner contract."""
        return validate(
            self.settings.envelope(
                "agent.result",
                {
                    "operation": request["body"]["operation"],
                    "target": request["body"]["target"],
                    "runId": run_id,
                    "state": state,
                    "output": output,
                    "problem": problem(code) if code else None,
                },
                request,
            )
        )

    def save(self, actor: str, request: Json, response: Json) -> None:
        """Persist only strictly projected, credential-free protocol data."""
        with self.database() as db:
            db.execute(
                "UPDATE requests SET response=? WHERE actor=? AND request_id=?",
                (json.dumps(response), actor, request["requestId"]),
            )

    async def run(
        self,
        actor: str,
        request: Json,
        run_id: str,
        authorize: Authorize,
        deadline: float,
        recheck: Recheck,
    ) -> Json:
        """Discard results after revocation or epoch rotation; retain final read outcome."""

        expected = seal(request)
        closed = False

        async def dispatch(frame: Json) -> Json:
            check_seal(frame, expected)
            self.check_local(frame, deadline)
            if closed or run_id in self.cancel_requested:
                raise asyncio.CancelledError
            self.commit(frame, recheck, deadline)
            stopped = asyncio.Event()
            self.native_pending[run_id] = stopped
            try:
                output = await self.handler(read_view(frame))
                check_seal(frame, expected)
                self.check_local(frame, deadline)
                if closed or run_id in self.cancel_requested:
                    raise asyncio.CancelledError
                response = self.result(frame, run_id, "completed", output)
                self.commit(frame, recheck, deadline)
                return response
            finally:
                stopped.set()
                self.native_pending.pop(run_id, None)
                self.release_cancel_state(run_id)

        async def authorized(frame: Json) -> bool:
            check_seal(frame, expected)
            await self.check(frame, authorize, deadline, recheck=recheck)
            return True

        try:
            worker = asyncio.create_task(
                guard_read(
                    request,
                    authorize=authorized,
                    handler=dispatch,
                    generation=self.settings.current_generation,
                )
            )
            self.workers[run_id] = worker
            worker.add_done_callback(lambda task: self.worker_stopped(run_id, task))
            if run_id in self.cancel_requested:
                worker.cancel()
            # wait_for can be defeated by a coroutine that swallows cancellation.
            # A separate supervisor reports TIMEOUT without waiting for its cleanup.
            done, _ = await asyncio.wait(
                {worker}, timeout=max(0, deadline - asyncio.get_running_loop().time())
            )
            if not done:
                worker.cancel()
                raise ContractError("TIMEOUT")
            response = worker.result()
            check_seal(request, expected)
            self.commit(request, recheck, deadline)
            if run_id in self.cancel_requested:
                response = self.result(request, run_id, "cancelled")
        except asyncio.CancelledError:
            worker.cancel()
            stopped = self.native_pending.get(run_id)
            if stopped is not None:
                confirmation = asyncio.create_task(stopped.wait())
                confirmed, _ = await asyncio.wait(
                    {confirmation},
                    timeout=max(0, deadline - asyncio.get_running_loop().time()),
                )
                if not confirmed:
                    confirmation.cancel()
            response = (
                self.result(request, run_id, "cancelled")
                if worker.done() and run_id not in self.native_pending
                else self.error(request, "OUTCOME_UNKNOWN")
            )
        except ContractError as error:
            response = self.error(request, error.code)
        except Exception:  # noqa: BLE001 -- native exception details must not cross the adapter boundary.
            logger.warning("Native interop read failed: %s", self.settings.operation)
            response = self.error(request, "INTERNAL")
        try:
            self.save(actor, request, response)
        except sqlite3.Error:
            response = self.error(request, "UNAVAILABLE")
        finally:
            closed = True
            self.active.pop(run_id, None)
            self.release_cancel_state(run_id)
        return response

    def worker_stopped(self, run_id: str, task: asyncio.Task[Json]) -> None:
        """Keep late cleanup bounded and discard its output after the response closes."""
        self.workers.pop(run_id, None)
        self.release_cancel_state(run_id)
        if not task.cancelled():
            task.exception()

    def release_cancel_state(self, run_id: str) -> None:
        """A stopped SDK task alone cannot confirm that native read cleanup has ended."""
        if (
            run_id not in self.active
            and run_id not in self.workers
            and run_id not in self.native_pending
        ):
            self.cancel_requested.discard(run_id)

    async def exchange(
        self,
        text: str,
        actor_id: str,
        authorize: Authorize,
        *,
        recheck: Recheck,
        respond_async: bool = False,
    ) -> Json:
        """Parse exact SDK JSON, check authority, negotiate, dispatch, replay or soft-cancel."""
        started = asyncio.get_running_loop().time()
        try:
            request = parse(text)
        except OverflowError:
            raise ContractError("SCHEMA_INVALID") from None
        deadline = (
            started
            + request["body"].get("timeoutMs", 5000) / 1000
        )
        namespace = json.dumps(
            {"nativeActor": actor_id, "target": self.settings.target()},
            sort_keys=True,
            separators=(",", ":"),
        )
        actor = hashlib.sha256(namespace.encode()).hexdigest()
        response: Json | None = None
        try:
            await self.check(request, authorize, deadline, recheck=recheck)
            kind, body = request["kind"], request["body"]
            if kind == "negotiate.request":
                response = self.settings.envelope(
                    "negotiate.response",
                    {
                        "selectedVersion": VERSION,
                        "capabilities": [self.settings.capability(self.available)],
                        "executionEnabled": False,
                    },
                    request,
                )
                await self.check(request, authorize, deadline, recheck=recheck)
                return self.deliver(request, response, recheck, deadline)
            if kind not in {"agent.request", "agent.cancel"}:
                raise ContractError("EXECUTION_DISABLED")
            if body["target"] != self.settings.target():
                raise ContractError("BINDING_MISMATCH")
            if kind == "agent.request":
                if body["operation"] != self.settings.operation:
                    raise ContractError("NO_ADAPTER")
                if body["capabilityRef"] is not None or body["approvalRef"] is not None:
                    raise ContractError("DENIED")
                if body["expectedResourceRevision"] is not None:
                    raise ContractError("REVISION_CONFLICT")
                if not self.available:
                    raise ContractError("NO_ADAPTER")
            with self.database() as db:
                previous = db.execute(
                    "SELECT * FROM requests WHERE actor=? AND request_id=?",
                    (actor, request["requestId"]),
                ).fetchone()
                if previous:
                    old = parse(previous["request"])
                    if (
                        old["kind"] != kind
                        or compare_request_reuse(old, request) != "replay"
                    ):
                        raise ContractError("IDEMPOTENCY_CONFLICT")
                    if previous["response"]:
                        response = parse(previous["response"])
                    else:
                        response = None
                else:
                    response = None
            if previous:
                if response is None:
                    task = self.active.get(previous["run_id"])
                    if task is None:
                        raise ContractError("OUTCOME_UNKNOWN")
                    if respond_async:
                        await self.check(request, authorize, deadline, recheck=recheck)
                        return self.deliver(
                            request, self.result(request, previous["run_id"], "running"),
                            recheck, deadline,
                        )
                    response = await asyncio.shield(task)
                await self.check(request, authorize, deadline, recheck=recheck)
                return self.deliver(request, response, recheck, deadline)
            if kind == "agent.cancel":
                return await self.cancel(actor, request, authorize, deadline, recheck)
            if (
                len(
                    self.active.keys()
                    | self.workers.keys()
                    | self.native_pending.keys()
                )
                >= 8
            ):
                raise ContractError("UNAVAILABLE")
            run_id = str(uuid4())
            self.reserve(actor, request, run_id)
            task = asyncio.create_task(
                self.run(actor, request, run_id, authorize, deadline, recheck)
            )
            self.active[run_id] = task
            if respond_async:
                await asyncio.sleep(0)
                await self.check(request, authorize, deadline, recheck=recheck)
                return self.deliver(
                    request, self.result(request, run_id, "accepted"), recheck, deadline
                )
            response = await asyncio.shield(task)
            await self.check(request, authorize, deadline, recheck=recheck)
            return self.deliver(request, response, recheck, deadline)
        except ContractError as error:
            return self.error(request, error.code)
        except sqlite3.Error:
            return self.error(request, "UNAVAILABLE")

    def reserve(self, actor: str, request: Json, run_id: str) -> None:
        """Bound journal retention to 128 entries without evicting unfinished reads."""
        with self.database() as db:
            count = db.execute("SELECT COUNT(*) FROM requests").fetchone()[0]
            if count >= 128:
                db.execute(
                    "DELETE FROM requests WHERE rowid IN (SELECT rowid FROM requests "
                    "WHERE response IS NOT NULL ORDER BY rowid LIMIT ?)",
                    (count - 127,),
                )
                if db.execute("SELECT COUNT(*) FROM requests").fetchone()[0] >= 128:
                    raise ContractError("UNAVAILABLE")
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?,NULL)",
                (actor, request["requestId"], json.dumps(request), run_id),
            )

    async def cancel(
        self, actor: str, request: Json, authorize: Authorize, deadline: float,
        recheck: Recheck,
    ) -> Json:
        """Freshly check the original owner and admit soft cancellation of a read."""
        run_id = request["body"]["runId"]
        with self.database() as db:
            candidates = db.execute(
                "SELECT * FROM requests WHERE actor=? AND run_id=?", (actor, run_id)
            ).fetchall()
        original = next(
            (
                parse(row["request"])
                for row in candidates
                if parse(row["request"])["kind"] == "agent.request"
            ),
            None,
        )
        if original is None:
            raise ContractError("DENIED")
        await self.check(original, authorize, deadline, recheck=recheck)
        task = self.active.get(run_id)
        if task is None:
            raise ContractError("CANCEL_NOT_CONFIRMED")
        worker = self.workers.get(run_id)
        if worker is not None and worker.done():
            raise ContractError("CANCEL_NOT_CONFIRMED")
        self.reserve(actor, request, run_id)
        self.commit(request, recheck, deadline)
        self.cancel_requested.add(run_id)
        if worker is not None:
            worker.cancel()
        response = self.result(original, run_id, "cancel_requested")
        response.update({key: request[key] for key in ("requestId", "correlationId")})
        await self.check(request, authorize, deadline, recheck=recheck)
        self.save(actor, request, response)
        return self.deliver(request, response, recheck, deadline)
