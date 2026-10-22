"""Clash/Mihomo controller integration and optional owned kernel service.

The controller API is deliberately a small, typed surface over the Mihomo
external-controller API.  In particular, this module never exposes the raw
controller response because proxy providers and connection metadata can carry
subscription credentials or other sensitive values.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import ipaddress
import math
import os
import re
import secrets as secret_module
import shutil
import socket
import subprocess
import time
import urllib.parse
import uuid
from pathlib import Path
from typing import Any, Literal, Mapping

import httpx
import yaml
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.managed_service import ManagedService, child_environment, executable
from core.service_state import ServiceState


CLASH_SETTINGS_ID = "clash"
CLASH_MANAGED_SETTINGS_ID = "clash-managed"
CLASH_PROFILE_KIND = "clash-profile"
CLASH_PROCESS_KEY = "mihomo"
DEFAULT_DELAY_URL = "https://www.gstatic.com/generate_204"
MAX_PROFILE_BYTES = 4 * 1024 * 1024
MAX_PROFILE_COUNT = 64
MAX_CONTROLLER_SECRET_LENGTH = 512
MAX_CONTROLLER_BODY_BYTES = 8 * 1024 * 1024
MAX_CONNECTIONS = 4096
MAX_PROCESS_NAME_LENGTH = 256
LOOPBACK_NAMES = {"localhost"}
VALID_MODES = ("rule", "global", "direct")
VALID_LOG_LEVELS = ("silent", "error", "warning", "info", "debug")


class ClashSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    controller_url: str = Field(min_length=1, max_length=2048)
    secret: str | None = Field(default=None, max_length=MAX_CONTROLLER_SECRET_LENGTH)
    clear_secret: bool = False

    @field_validator("secret")
    @classmethod
    def valid_secret(cls, value: str | None) -> str | None:
        if value is not None and any(ord(char) < 32 or ord(char) >= 127 for char in value):
            raise ValueError("secret 包含无效字符")
        return value


class ClashConfigPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    mode: Literal["rule", "global", "direct"] | None = None
    log_level: Literal["silent", "error", "warning", "info", "debug"] | None = None


class ProxySelection(BaseModel):
    # Proxy names are user-defined identifiers; surrounding spaces can be
    # meaningful and must survive the JSON body unchanged.
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=512)


class ClashProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=MAX_PROFILE_BYTES)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        if value in {".", ".."} or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("profile 名称包含无效字符")
        if "/" in value or "\\" in value:
            raise ValueError("profile 名称不能包含路径分隔符")
        return value


class ClashProfileStart(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    profile_id: str = Field(min_length=1, max_length=128)


def _loopback(host: str) -> bool:
    if host.lower().rstrip(".") in LOOPBACK_NAMES:
        return True
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(address.is_loopback or getattr(address, "ipv4_mapped", None) and address.ipv4_mapped.is_loopback)


def normalize_controller_url(value: str) -> str:
    """Validate controller origin and enforce HTTP loopback-only access."""
    if not isinstance(value, str):
        raise HTTPException(422, "Clash 控制器地址无效")
    value = value.strip()
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise HTTPException(422, "Clash 控制器地址无效") from None
    if parsed.scheme not in {"http", "https"} or not hostname:
        raise HTTPException(422, "Clash 控制器地址必须使用 http 或 https")
    if parsed.username is not None or parsed.password is not None:
        raise HTTPException(422, "Clash 控制器地址不能包含用户凭据")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise HTTPException(422, "Clash 控制器地址只能包含协议、主机和端口")
    if port is not None and not 1 <= port <= 65535:
        raise HTTPException(422, "Clash 控制器端口无效")
    if parsed.scheme == "http" and not _loopback(hostname):
        raise HTTPException(422, "HTTP 控制器必须绑定 loopback；远程控制器请使用 HTTPS")
    host = hostname.lower().rstrip(".")
    # urlsplit().hostname strips IPv6 brackets, so restore them for a valid URL.
    display_host = f"[{host}]" if ":" in host else host
    default_port = (parsed.scheme == "http" and port == 80) or (parsed.scheme == "https" and port == 443)
    suffix = "" if port is None or default_port else f":{port}"
    return f"{parsed.scheme}://{display_host}{suffix}"


def _safe_path_name(value: str, label: str = "名称") -> str:
    """Validate a decoded path name before it is encoded into a controller URL."""
    if not isinstance(value, str):
        raise HTTPException(400, f"{label}无效")
    if not value or len(value) > 512 or value in {".", ".."}:
        raise HTTPException(400, f"{label}无效")
    if "\x00" in value or "\\" in value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise HTTPException(400, f"{label}无效")
    return value


def encoded_path_name(value: str, label: str = "名称") -> str:
    return urllib.parse.quote(_safe_path_name(value, label), safe="")


def _number(value: Any, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, float) and not math.isfinite(value):
        return default
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return default


def _traffic_counter(payload: Mapping[str, Any], key: str) -> int:
    """Validate a controller traffic counter instead of silently coercing it."""
    value = payload.get(key)
    if key not in payload or isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HTTPException(502, "Clash 控制器 traffic 快照无效")
    if isinstance(value, float) and (not math.isfinite(value) or not value.is_integer()):
        raise HTTPException(502, "Clash 控制器 traffic 快照无效")
    try:
        counter = int(value)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(502, "Clash 控制器 traffic 快照无效") from None
    if counter < 0:
        raise HTTPException(502, "Clash 控制器 traffic 快照无效")
    return counter


def _optional_number(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def sanitize_proxy(proxy: Any) -> dict[str, Any]:
    """Return only the safe, UI-required fields from a Mihomo proxy object."""
    if not isinstance(proxy, Mapping):
        return {"name": "", "type": ""}
    result: dict[str, Any] = {
        "name": str(proxy.get("name", ""))[:512],
        "type": str(proxy.get("type", ""))[:128],
    }
    if isinstance(proxy.get("now"), str):
        result["now"] = proxy["now"][:512]
    members = proxy.get("all")
    if isinstance(members, list):
        result["all"] = [str(item)[:512] for item in members[:2048] if isinstance(item, (str, int, float))]
    history = proxy.get("history")
    if isinstance(history, list):
        result["history"] = [
            {"time": str(item.get("time", ""))[:128], "delay": _number(item.get("delay"))}
            for item in history[:2048]
            if isinstance(item, Mapping)
        ]
    if isinstance(proxy.get("alive"), bool):
        result["alive"] = proxy["alive"]
    return result


def sanitize_provider(provider: Any) -> dict[str, Any]:
    if not isinstance(provider, Mapping):
        return {"name": "", "type": "", "vehicleType": ""}
    result: dict[str, Any] = {
        "name": str(provider.get("name", ""))[:512],
        "type": str(provider.get("type", ""))[:128],
        "vehicleType": str(provider.get("vehicleType", ""))[:128],
    }
    if provider.get("updatedAt") is not None:
        result["updatedAt"] = str(provider.get("updatedAt"))[:128]
    subscription = provider.get("subscriptionInfo")
    if isinstance(subscription, Mapping):
        # These are aggregate counters only.  Never forward unrecognised fields
        # because provider implementations sometimes include URLs or tokens.
        result["subscriptionInfo"] = {
            key: subscription[key]
            for key in ("Upload", "Download", "Total", "Expire")
            if key in subscription and isinstance(subscription[key], (str, int, float, type(None)))
        }
    proxies = provider.get("proxies")
    if isinstance(proxies, list):
        result["proxies"] = [sanitize_proxy(proxy) for proxy in proxies[:4096]]
    return result


def sanitize_connection(connection: Any) -> dict[str, Any]:
    if not isinstance(connection, Mapping):
        return {
            "id": "",
            "start": "",
            "upload": 0,
            "download": 0,
            "chains": [],
            "rule": "",
            "metadata": {},
        }
    metadata = connection.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    allowed_metadata = (
        "network",
        "type",
        "sourceIP",
        "sourcePort",
        "destinationIP",
        "destinationPort",
        "host",
    )
    clean_metadata: dict[str, Any] = {}
    for key in allowed_metadata:
        value = metadata.get(key)
        if value is None:
            continue
        if key.endswith("Port"):
            clean_metadata[key] = _number(value)
        else:
            clean_metadata[key] = str(value)[:1024]
    chains = connection.get("chains")
    clean_chains = [str(item)[:512] for item in chains[:256] if isinstance(item, (str, int, float))] if isinstance(chains, list) else []
    return {
        "id": str(connection.get("id", ""))[:512],
        "start": str(connection.get("start", ""))[:128],
        "upload": _number(connection.get("upload")),
        "download": _number(connection.get("download")),
        "chains": clean_chains,
        "rule": str(connection.get("rule", ""))[:512],
        "metadata": clean_metadata,
    }


def _safe_process_name(value: Any) -> str | None:
    """Keep only a basename-like process label for traffic grouping."""
    if not isinstance(value, str):
        return None
    value = value.strip()
    if (
        not value
        or len(value) > MAX_PROCESS_NAME_LENGTH
        or "/" in value
        or "\\" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        return None
    return value


def sanitize_traffic_connection(connection: Any) -> dict[str, Any]:
    """Project a connection while extending the safe metadata allowlist."""
    result = sanitize_connection(connection)
    metadata = connection.get("metadata") if isinstance(connection, Mapping) else None
    clean_metadata = dict(result["metadata"])
    process_name = None
    if isinstance(metadata, Mapping):
        for key in ("process", "processName", "process_name"):
            process_name = _safe_process_name(metadata.get(key))
            if process_name is not None:
                break
    if process_name is not None:
        clean_metadata["process"] = process_name
    result["metadata"] = clean_metadata
    return result


def sanitize_configs(payload: Any) -> dict[str, Any]:
    payload = payload if isinstance(payload, Mapping) else {}
    tun = payload.get("tun") if isinstance(payload.get("tun"), Mapping) else {}
    return {
        "mode": payload.get("mode") if isinstance(payload.get("mode"), str) else None,
        "log_level": (payload.get("log-level") if isinstance(payload.get("log-level"), str)
                       else payload.get("log_level") if isinstance(payload.get("log_level"), str)
                       else None),
        "mixed_port": _optional_number(payload.get("mixed-port", payload.get("mixed_port"))),
        "port": _optional_number(payload.get("port")),
        "socks_port": _optional_number(payload.get("socks-port", payload.get("socks_port"))),
        "allow_lan": bool(payload.get("allow-lan", payload.get("allow_lan", False))),
        "tun_enabled": bool(tun.get("enable", payload.get("tun-enabled", payload.get("tun_enabled", False)))),
    }


def sanitize_rules(payload: Any) -> list[dict[str, str]]:
    raw_rules = payload.get("rules", []) if isinstance(payload, Mapping) else []
    if not isinstance(raw_rules, list):
        return []
    return [
        {
            "type": str(item.get("type", ""))[:128],
            "payload": str(item.get("payload", ""))[:2048],
            "proxy": str(item.get("proxy", ""))[:512],
        }
        for item in raw_rules[:10000]
        if isinstance(item, Mapping)
    ]


def _safe_delay_url() -> str:
    value = os.getenv("R_LINK_CLASH_TEST_URL", DEFAULT_DELAY_URL).strip() or DEFAULT_DELAY_URL
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        raise HTTPException(503, "Clash 延迟测试地址配置无效") from None
    if parsed.scheme not in {"http", "https"} or not hostname or parsed.username or parsed.password or parsed.fragment:
        raise HTTPException(503, "Clash 延迟测试地址配置无效")
    if port is not None and not 1 <= port <= 65535:
        raise HTTPException(503, "Clash 延迟测试地址配置无效")
    return value


class _LimitedSafeLoader(yaml.SafeLoader):
    """SafeLoader with conservative alias/node limits for uploaded profiles."""

    _alias_count = 0
    _node_count = 0

    def __init__(self, stream: Any) -> None:
        super().__init__(stream)
        self._alias_count = 0
        self._node_count = 0

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            self._alias_count += 1
            if self._alias_count > 256:
                raise yaml.YAMLError("too many YAML aliases")
        self._node_count += 1
        if self._node_count > 100_000:
            raise yaml.YAMLError("too many YAML nodes")
        return super().compose_node(parent, index)


def _profile_config(content: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > MAX_PROFILE_BYTES:
        raise HTTPException(413, "Clash profile 超过大小限制")
    try:
        value = yaml.load(content, Loader=_LimitedSafeLoader)
    except (yaml.YAMLError, RecursionError):
        raise HTTPException(422, "Clash profile YAML 无法解析") from None
    if not isinstance(value, dict):
        raise HTTPException(422, "Clash profile 顶层必须是对象")
    _reject_yaml_cycles(value)
    return value


def _reject_yaml_cycles(value: Any, active: set[int] | None = None, depth: int = 0,
                        visited: set[int] | None = None) -> None:
    """Reject recursive YAML aliases before copying/dumping the profile."""
    if depth > 128:
        raise HTTPException(422, "Clash profile 嵌套层级过深")
    if not isinstance(value, (Mapping, list, tuple)):
        return
    active = set() if active is None else active
    visited = set() if visited is None else visited
    marker = id(value)
    if marker in active:
        raise HTTPException(422, "Clash profile 不能包含递归 YAML 别名")
    if marker in visited:
        return
    active.add(marker)
    try:
        if isinstance(value, Mapping):
            for key, child in value.items():
                _reject_yaml_cycles(key, active, depth + 1, visited)
                _reject_yaml_cycles(child, active, depth + 1, visited)
        else:
            for child in value:
                _reject_yaml_cycles(child, active, depth + 1, visited)
    finally:
        active.remove(marker)
        visited.add(marker)


def _write_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        temporary.replace(path)
    except BaseException:
        try:
            os.close(fd)
        except OSError:
            pass
        temporary.unlink(missing_ok=True)
        raise


def _profile_identifier(value: str) -> str:
    # ServiceState-generated IDs are UUIDs.  Keep the validator slightly wider
    # for migrated local data while still rejecting path traversal.
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise HTTPException(400, "profile 编号无效")
    return value


def _owned_profile_path(state: ServiceState, identifier: str) -> Path:
    identifier = _profile_identifier(identifier)
    root = (state.root / "clash-profiles").resolve()
    path = (root / f"{identifier}.yaml").resolve()
    if path.parent != root:
        raise HTTPException(400, "profile 路径无效")
    return path


def _owned_profile_runtime_dir(process_dir: Path, identifier: str) -> Path:
    identifier = _profile_identifier(identifier)
    root = (process_dir / "profiles").resolve()
    path = (root / identifier).resolve()
    if path.parent != root:
        raise HTTPException(400, "profile 运行目录无效")
    return path


def _free_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


def _sensitive_values(value: Any, key: str = "", visited: set[int] | None = None) -> tuple[str, ...]:
    """Collect likely credential scalars for ManagedService log redaction."""
    result: list[str] = []
    visited = set() if visited is None else visited
    if isinstance(value, (Mapping, list)):
        if id(value) in visited:
            return ()
        visited.add(id(value))
    lowered = key.lower()
    sensitive_key = any(token in lowered for token in ("password", "passwd", "secret", "token", "uuid", "psk", "private-key", "client-key", "credential"))
    if sensitive_key and isinstance(value, (str, int, float)):
        text = str(value)
        if text:
            result.append(text)
    if isinstance(value, Mapping):
        for child_key, child_value in value.items():
            result.extend(_sensitive_values(child_value, str(child_key), visited))
    elif isinstance(value, list):
        for child_value in value:
            result.extend(_sensitive_values(child_value, key, visited))
    return tuple(dict.fromkeys(result))


def _normalize_managed_config(config: Mapping[str, Any], controller: str, secret: str, profile_dir: Path,
                              mixed_port: int | None = None) -> dict[str, Any]:
    """Constrain imported profiles to a local, non-interfering kernel."""
    normalized = copy.deepcopy(dict(config))
    parsed_controller = urllib.parse.urlsplit(controller)
    controller_host = parsed_controller.hostname or "127.0.0.1"
    display_host = f"[{controller_host}]" if ":" in controller_host else controller_host
    controller_port = parsed_controller.port
    normalized["external-controller"] = f"{display_host}:{controller_port}"
    normalized["secret"] = secret
    normalized["allow-lan"] = False
    normalized["bind-address"] = "127.0.0.1"

    if mixed_port is not None:
        # Imported profiles often use the live client's ports. Give this
        # independent instance its own inlet, so both processes can coexist.
        normalized["mixed-port"] = mixed_port
        normalized["port"] = 0
        normalized["socks-port"] = 0

    # These settings can affect the host outside the owned process.  The
    # imported profile remains available for ordinary proxy configuration, but
    # system/TUN/DNS/listener side effects are disabled for managed mode.
    tun = normalized.get("tun")
    if not isinstance(tun, dict):
        tun = {}
        normalized["tun"] = tun
    tun["enable"] = False
    dns = normalized.get("dns")
    if isinstance(dns, dict):
        dns["enable"] = False
        dns.pop("listen", None)
    normalized.pop("listeners", None)
    normalized.pop("script", None)
    normalized.pop("hooks", None)
    normalized.pop("post-up", None)
    normalized.pop("post-down", None)
    for key in (
        "external-controller-unix",
        "external-controller-pipe",
        "external-controller-tls",
        "external-ui",
        "external-ui-name",
        "external-ui-url",
        "external-doh-server",
        "redir-port",
        "tproxy-port",
        "ss-config",
        "vmess-config",
        "tuic-server",
    ):
        normalized.pop(key, None)
    ntp = normalized.get("ntp")
    if isinstance(ntp, dict):
        ntp["write-to-system"] = False
    # Legacy top-level inbound server sections can open listeners independently
    # from the normal HTTP/SOCKS/mixed ports.  Managed mode has no such ports.
    for key in ("ss", "vmess", "vless", "trojan", "hysteria", "hysteria2", "tuic", "socks", "http", "redir", "tproxy", "mixed"):
        normalized.pop(key, None)

    # Provider caches are kept under the service data directory.  This avoids
    # following profile supplied paths into arbitrary host locations.
    provider_root = (profile_dir / "providers").resolve()
    provider_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    for section in ("proxy-providers", "rule-providers"):
        providers = normalized.get(section)
        if not isinstance(providers, dict):
            continue
        for name, provider in providers.items():
            if not isinstance(provider, dict):
                continue
            provider_name = str(name)
            safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", provider_name)[:96] or "provider"
            digest = hashlib.sha256(f"{section}:{provider_name}".encode("utf-8")).hexdigest()[:12]
            provider["path"] = str(provider_root / f"{safe_name}-{digest}.yaml")
    profile = normalized.get("profile")
    if isinstance(profile, dict):
        profile["store-selected"] = bool(profile.get("store-selected", False))
    return normalized


class ClashManager:
    """Own controller settings and at most one Mihomo process."""

    def __init__(self, state: ServiceState):
        self.state = state
        self.process = ManagedService(state, CLASH_PROCESS_KEY)
        self.lock = asyncio.Lock()
        self._managed_target: dict[str, str] | None = None
        self._managed_profile_id: str | None = None
        self._traffic_target_revision = 0

    def _setting(self) -> dict[str, Any] | None:
        return next((item for item in self.state.list("settings") if item.get("id") == CLASH_SETTINGS_ID), None)

    def _managed_setting(self) -> dict[str, Any] | None:
        return next((item for item in self.state.list("settings") if item.get("id") == CLASH_MANAGED_SETTINGS_ID), None)

    def settings(self) -> dict[str, Any]:
        item = self._setting() or {}
        return {
            "controller_url": str(item.get("controller_url") or ""),
            "has_secret": bool(item.get("secret")),
        }

    async def save_settings(self, data: ClashSettingsInput) -> dict[str, Any]:
        controller_url = normalize_controller_url(data.controller_url)
        async with self.lock:
            current = self._setting() or {}
            current_secret = current.get("secret") if isinstance(current.get("secret"), str) else None
            submitted_secret = data.secret if isinstance(data.secret, str) else None
            secret = current_secret
            if submitted_secret:
                secret = submitted_secret
            elif data.clear_secret:
                secret = None
            if controller_url.startswith("https://") and not _loopback(urllib.parse.urlsplit(controller_url).hostname or "") and not secret:
                raise HTTPException(422, "远程 HTTPS 控制器必须配置 secret")
            if (current.get("controller_url"), current.get("secret")) != (controller_url, secret):
                self._traffic_target_revision += 1
            self.state.save("settings", {"controller_url": controller_url, "secret": secret}, CLASH_SETTINGS_ID)
            self.state.audit("clash.settings", CLASH_SETTINGS_ID)
            return self.settings()

    def _external_target(self) -> tuple[str, str | None] | None:
        item = self._setting()
        if not item or not item.get("controller_url"):
            return None
        return str(item["controller_url"]), item.get("secret") if isinstance(item.get("secret"), str) else None

    def _target(self) -> tuple[str, str | None] | None:
        if self.process.status()["state"] == "running" and self._managed_target:
            return self._managed_target["controller_url"], self._managed_target["secret"]
        return self._external_target()

    def _traffic_target_context(
        self,
        target: tuple[str, str | None] | None = None,
    ) -> tuple[tuple[str, str | None], str, int, int | None] | None:
        target = self._target() if target is None else target
        if not target:
            return None
        process = self.process.status()
        managed = process["state"] == "running" and self._managed_target is not None
        pid = process.get("pid") if managed else None
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            pid = None
        return target, "managed" if managed else "external", self._traffic_target_revision, pid

    def _traffic_source_id(
        self,
        context: tuple[tuple[str, str | None], str, int, int | None] | None = None,
    ) -> str | None:
        """Return an opaque, non-secret identifier for a captured target."""
        context = self._traffic_target_context() if context is None else context
        if not context:
            return None
        target, target_kind, revision, pid = context
        controller_url = target[0]
        material = f"clash-traffic-v1\0{target_kind}\0{controller_url}\0{revision}\0{pid or ''}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()
        return f"clash-src-v1-{digest}"

    def managed_status(self) -> dict[str, Any]:
        process = self.process.status()
        available = process["state"] == "running"
        if not available:
            try:
                executable("R_LINK_MIHOMO_BINARY", "mihomo")
                available = True
            except HTTPException:
                available = False
        return {
            "available": available,
            "state": process["state"],
            "pid": process["pid"],
            "error": process["error"],
            "profile_id": self._managed_profile_id,
        }

    async def status(self) -> dict[str, Any]:
        target = self._target()
        managed = self.managed_status()
        result: dict[str, Any] = {
            "configured": bool(target),
            "connected": False,
            "controller_url": target[0] if target else "",
            "version": None,
            "error": None,
            "managed": managed,
        }
        if not target:
            return result
        try:
            payload = await self._json_request("GET", "/version")
            version = payload.get("version") if isinstance(payload, Mapping) else None
            if isinstance(version, str) and version.strip():
                result["connected"] = True
                result["version"] = version.strip()[:256]
            else:
                result["error"] = "Clash 控制器版本响应无效"
        except HTTPException as exc:
            result["error"] = str(exc.detail)
        return result

    async def _response(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Mapping[str, Any] | None = None,
        timeout: float = 10,
        target: tuple[str, str | None] | None = None,
    ) -> httpx.Response:
        target = self._target() if target is None else target
        if not target:
            raise HTTPException(409, "尚未配置 Clash 控制器")
        base_url, secret = target
        url = base_url.rstrip("/") + "/" + path.lstrip("/")
        headers = {"Accept": "application/json"}
        if secret:
            headers["Authorization"] = "Bearer " + secret
        try:
            async with httpx.AsyncClient(timeout=timeout, trust_env=False) as client:
                # Mihomo responses are JSON, but an upstream failure or future
                # endpoint must not make the R-Link worker buffer unbounded data.
                async with client.stream(method, url, headers=headers, json=json_body, params=params) as upstream:
                    content = bytearray()
                    async for chunk in upstream.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_CONTROLLER_BODY_BYTES:
                            raise HTTPException(502, "Clash 控制器响应过大")
                    response_headers = dict(upstream.headers)
                    # aiter_bytes() returns decompressed content; do not carry
                    # stale framing/encoding headers into the reconstructed
                    # bounded response.
                    for header in ("content-encoding", "content-length", "transfer-encoding"):
                        response_headers.pop(header, None)
                    response = httpx.Response(
                        upstream.status_code,
                        headers=response_headers,
                        content=bytes(content),
                        request=upstream.request,
                    )
        except HTTPException:
            raise
        except (httpx.HTTPError, OSError):
            raise HTTPException(503, "无法连接 Clash 控制器") from None
        if response.status_code in {401, 403}:
            raise HTTPException(502, "Clash 控制器认证失败")
        if response.status_code == 404:
            raise HTTPException(404, "Clash 控制器未找到资源")
        if 300 <= response.status_code < 400:
            raise HTTPException(502, "Clash 控制器返回了重定向")
        if 400 <= response.status_code < 500:
            raise HTTPException(422, "Clash 控制器拒绝请求")
        if response.status_code >= 500:
            raise HTTPException(502, "Clash 控制器服务错误")
        return response

    async def _json_request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        params: Mapping[str, Any] | None = None,
        timeout: float = 10,
        target: tuple[str, str | None] | None = None,
    ) -> Any:
        response = await self._response(
            method,
            path,
            json_body=json_body,
            params=params,
            timeout=timeout,
            target=target,
        )
        if not response.content:
            return {}
        try:
            return response.json()
        except (ValueError, TypeError):
            raise HTTPException(502, "Clash 控制器返回了无效数据") from None

    async def configs(self) -> dict[str, Any]:
        return sanitize_configs(await self._json_request("GET", "/configs"))

    async def patch_configs(self, data: ClashConfigPatch) -> dict[str, Any]:
        if data.mode is None and data.log_level is None:
            raise HTTPException(422, "至少需要修改 mode 或 log_level")
        payload: dict[str, str] = {}
        if data.mode is not None:
            payload["mode"] = data.mode
        if data.log_level is not None:
            payload["log-level"] = data.log_level
        await self._response("PATCH", "/configs", json_body=payload)
        return await self.configs()

    async def proxies(self) -> dict[str, Any]:
        payload = await self._json_request("GET", "/proxies")
        raw = payload.get("proxies", {}) if isinstance(payload, Mapping) else {}
        if not isinstance(raw, Mapping):
            raw = {}
        return {"proxies": {str(name)[:512]: sanitize_proxy(value) for name, value in list(raw.items())[:4096]}}

    async def select_proxy(self, name: str, selection: ProxySelection) -> None:
        path_name = encoded_path_name(name, "代理组名称")
        selected = _safe_path_name(selection.name, "代理名称")
        await self._response("PUT", f"/proxies/{path_name}", json_body={"name": selected})

    async def proxy_delay(self, name: str, timeout: int) -> dict[str, int]:
        if isinstance(timeout, bool) or not 100 <= timeout <= 30000:
            raise HTTPException(422, "延迟测试 timeout 必须在 100–30000 毫秒之间")
        path_name = encoded_path_name(name, "代理名称")
        response = await self._json_request("GET", f"/proxies/{path_name}/delay",
                                            # Accept any successful HTTP response
                                            # from the fixed probe endpoint.  A
                                            # default mihomo build often
                                            # expects 204, while local/private
                                            # probes commonly return 200.
                                            params={"url": _safe_delay_url(), "timeout": timeout, "expected": "200-299"},
                                            timeout=max(10, min(35, timeout / 1000 + 5)))
        delay = response.get("delay") if isinstance(response, Mapping) else None
        if isinstance(delay, bool) or not isinstance(delay, (int, float)):
            raise HTTPException(502, "Clash 控制器未返回有效延迟")
        return {"delay": max(0, min(65535, int(delay)))}

    async def rules(self) -> dict[str, Any]:
        return {"rules": sanitize_rules(await self._json_request("GET", "/rules"))}

    async def connections(self) -> dict[str, Any]:
        payload = await self._json_request("GET", "/connections")
        payload = payload if isinstance(payload, Mapping) else {}
        connections = payload.get("connections", [])
        return {
            "downloadTotal": _number(payload.get("downloadTotal")),
            "uploadTotal": _number(payload.get("uploadTotal")),
            "connections": [sanitize_connection(item) for item in connections[:MAX_CONNECTIONS]] if isinstance(connections, list) else [],
        }

    async def traffic(self) -> dict[str, Any]:
        """Return one bounded, public traffic snapshot from /connections."""
        context = self._traffic_target_context()
        if context is None:
            raise HTTPException(409, "尚未配置 Clash 控制器")
        target = context[0]
        payload = await self._json_request("GET", "/connections", target=target)
        if self._traffic_target_context() != context:
            raise HTTPException(409, "Clash 控制器目标已变化，请重试")
        if not isinstance(payload, Mapping):
            raise HTTPException(502, "Clash 控制器 traffic 快照无效")
        download_total = _traffic_counter(payload, "downloadTotal")
        upload_total = _traffic_counter(payload, "uploadTotal")
        if "connections" not in payload:
            raise HTTPException(502, "Clash 控制器 traffic 快照无效")
        raw_connections = payload["connections"]
        if raw_connections is None:
            raw_connections = []
        elif not isinstance(raw_connections, list):
            raise HTTPException(502, "Clash 控制器 traffic 快照无效")
        total_connections = len(raw_connections)
        return {
            "sampled_at": float(time.time()),
            "source_id": self._traffic_source_id(context),
            "downloadTotal": download_total,
            "uploadTotal": upload_total,
            "connections": [sanitize_traffic_connection(item) for item in raw_connections[:MAX_CONNECTIONS]],
            "total_connections": total_connections,
            "truncated": total_connections > MAX_CONNECTIONS,
        }

    async def close_connections(self, identifier: str | None = None, source_id: str | None = None) -> None:
        if identifier is None:
            path = "/connections"
        else:
            path = "/connections/" + encoded_path_name(identifier, "连接编号")
        if source_id is None:
            await self._response("DELETE", path)
            return
        context = self._traffic_target_context()
        if context is None or source_id != self._traffic_source_id(context):
            raise HTTPException(409, "流量来源已变化，请刷新后重试")
        await self._response("DELETE", path, target=context[0])
        if self._traffic_target_context() != context:
            raise HTTPException(409, "流量来源已变化，请刷新后重试")

    async def providers(self) -> dict[str, Any]:
        payload = await self._json_request("GET", "/providers/proxies")
        raw = payload.get("providers", {}) if isinstance(payload, Mapping) else {}
        if not isinstance(raw, Mapping):
            raw = {}
        return {"providers": {str(name)[:512]: sanitize_provider(value) for name, value in list(raw.items())[:4096]}}

    async def refresh_provider(self, name: str) -> None:
        await self._response("PUT", "/providers/proxies/" + encoded_path_name(name, "代理提供者名称"))

    def _profile_item(self, identifier: str) -> dict[str, Any]:
        return self.state.get(CLASH_PROFILE_KIND, _profile_identifier(identifier))

    def profiles(self) -> list[dict[str, Any]]:
        running = self.process.status()["state"] == "running"
        return [
            {
                "id": item["id"],
                "name": item.get("name", ""),
                "active": bool(running and item["id"] == self._managed_profile_id),
                "updated_at": item.get("updated_at"),
            }
            for item in self.state.list(CLASH_PROFILE_KIND)
        ]

    async def save_profile(self, data: ClashProfileInput) -> dict[str, Any]:
        _profile_config(data.content)
        async with self.lock:
            if len(self.state.list(CLASH_PROFILE_KIND)) >= MAX_PROFILE_COUNT:
                raise HTTPException(409, "Clash profile 数量达到上限")
            identifier = str(uuid.uuid4())
            path = _owned_profile_path(self.state, identifier)
            _write_private_text(path, data.content)
            try:
                item = self.state.save(CLASH_PROFILE_KIND, {"name": data.name, "path": str(path)}, identifier)
            except BaseException:
                path.unlink(missing_ok=True)
                raise
            self.state.audit("clash.profile.save", identifier)
            return {"id": item["id"], "name": item["name"], "active": False, "updated_at": item["updated_at"]}

    async def delete_profile(self, identifier: str) -> None:
        identifier = _profile_identifier(identifier)
        async with self.lock:
            self._profile_item(identifier)
            if self.process.status()["state"] == "running" and self._managed_profile_id == identifier:
                raise HTTPException(409, "请先停止正在运行的 Clash profile")
            path = _owned_profile_path(self.state, identifier)
            self.state.delete(CLASH_PROFILE_KIND, identifier)
            path.unlink(missing_ok=True)
            runtime_dir = _owned_profile_runtime_dir(self.process.directory, identifier)
            if runtime_dir.is_symlink():
                runtime_dir.unlink(missing_ok=True)
            elif runtime_dir.is_dir():
                shutil.rmtree(runtime_dir)
            self.state.audit("clash.profile.delete", identifier)

    async def _validate_binary(self, binary: str, config_path: Path, work_dir: Path) -> None:
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                [binary, "-t", "-d", str(work_dir), "-f", str(config_path)],
                cwd=str(work_dir),
                env=child_environment(direct_network=True),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=20,
                check=False,
            )
        except subprocess.TimeoutExpired:
            raise HTTPException(504, "Mihomo 配置验证超时") from None
        except OSError:
            raise HTTPException(503, "Mihomo 配置验证程序无法启动") from None
        # Never include validator output: it can contain profile credentials.
        if result.returncode != 0:
            raise HTTPException(422, "Mihomo 配置验证失败")

    async def start_managed(self, identifier: str) -> dict[str, Any]:
        identifier = _profile_identifier(identifier)
        async with self.lock:
            profile = self._profile_item(identifier)
            if self.process.status()["state"] == "running":
                if self._managed_profile_id == identifier:
                    return self.managed_status()
                raise HTTPException(409, "已有 Mihomo profile 正在运行")
            binary = executable("R_LINK_MIHOMO_BINARY", "mihomo")
            path = _owned_profile_path(self.state, identifier)
            try:
                content = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                raise HTTPException(404, "Clash profile 文件不存在") from None
            config = _profile_config(content)
            profile_dir = (self.process.directory / "profiles" / identifier).resolve()
            profile_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            port = _free_loopback_port()
            mixed_port = _free_loopback_port()
            while mixed_port == port:
                mixed_port = _free_loopback_port()
            controller_url = f"http://127.0.0.1:{port}"
            managed_secret = secret_module.token_urlsafe(32)
            normalized = _normalize_managed_config(config, controller_url, managed_secret, profile_dir, mixed_port)
            candidate = self.process.directory / "mihomo.yaml"
            _write_private_text(candidate, yaml.safe_dump(normalized, allow_unicode=True, sort_keys=False))
            try:
                await self._validate_binary(binary, candidate, profile_dir)
                await self.process.stop()
                result = await self.process.start(
                    [binary, "-d", str(profile_dir), "-f", str(candidate)],
                    env=child_environment(direct_network=True),
                    secrets=(managed_secret,) + _sensitive_values(config),
                )
            except BaseException:
                await self.process.stop()
                candidate.unlink(missing_ok=True)
                raise
            self._managed_target = {"controller_url": controller_url, "secret": managed_secret}
            self._managed_profile_id = identifier
            self._traffic_target_revision += 1
            # Persist only non-secret metadata.  A restart recovers/kills the
            # owned PID via ManagedService but intentionally does not autostart.
            self.state.save("settings", {"profile_id": identifier, "controller_url": controller_url}, CLASH_MANAGED_SETTINGS_ID)
            self.state.audit("clash.managed.start", identifier)
            return dict(result, profile_id=identifier)

    async def stop_managed(self) -> dict[str, Any]:
        async with self.lock:
            await self.process.stop()
            self._managed_target = None
            profile_id = self._managed_profile_id
            self._managed_profile_id = None
            self._traffic_target_revision += 1
            self.state.delete("settings", CLASH_MANAGED_SETTINGS_ID) if self._managed_setting() else None
            (self.process.directory / "mihomo.yaml").unlink(missing_ok=True)
            self.state.audit("clash.managed.stop", profile_id or CLASH_PROCESS_KEY)
            return self.managed_status()

    async def recover(self) -> None:
        # recover_processes() has already terminated any stale owned PID.  Do
        # not reconnect to a process merely because its old settings remain.
        self._managed_target = None
        self._managed_profile_id = None
        self._traffic_target_revision += 1
        if self._managed_setting():
            self.state.delete("settings", CLASH_MANAGED_SETTINGS_ID)

    async def close(self) -> None:
        async with self.lock:
            await self.process.stop()
            self._managed_target = None
            self._managed_profile_id = None
            self._traffic_target_revision += 1
            (self.process.directory / "mihomo.yaml").unlink(missing_ok=True)


# Compatibility alias for callers that use the service terminology.
ClashService = ClashManager
