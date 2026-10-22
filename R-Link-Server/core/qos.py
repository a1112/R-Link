"""Safe Linux tc/HTB/IFB device bandwidth shaping.

The QoS manager deliberately owns only objects that it can identify with a
private marker and deterministic handles.  It never invokes a shell and it
never replaces an unknown root qdisc, ingress qdisc, clsact, or IFB.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import math
import os
import platform as platform_module
import re
import secrets
import shutil
import socket
import stat
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


QOS_CONFIG_KIND = "qos-config"
QOS_APPLIED_KIND = "qos-applied"
QOS_RECORD_ID = "qos"
QOS_MARKER_VERSION = 1
QOS_OWNER = "r-link-qos-v1"
QOS_BACKEND = "linux-tc-htb-ifb"
QOS_DEFAULT_CLASS_RATE = "1kbit"
QOS_DEFAULT_CLASS_Mbps = 0.001
QOS_MAX_POLICIES = 64
QOS_MAX_COMMAND_OUTPUT = 256 * 1024
QOS_COMMAND_TIMEOUT = 8.0
# Keep the first byte alphanumeric so an interface name can never be
# interpreted as an option by a future argv consumer.  Linux IFNAMSIZ leaves
# at most 15 visible bytes.
QOS_IFACE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,14}$")
QOS_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
QOS_ALIAS_RE = re.compile(r"^r-link-qos-[0-9a-f]{32}$")
QOS_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class QosCommandError(RuntimeError):
    """Internal safe error; stderr is deliberately never exposed."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def _strict_number(value: Any, *, minimum: float, maximum: float | None = None,
                   allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("必须是数字")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("数字范围无效") from None
    if not math.isfinite(number) or number < minimum:
        raise ValueError("数字范围无效")
    if maximum is not None and number > maximum:
        raise ValueError("数字范围无效")
    return number


def _strict_revision(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("revision 必须是非负整数")
    return value


def _safe_text(value: Any, *, minimum: int, maximum: int, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label}无效")
    value = value.strip()
    if not minimum <= len(value) <= maximum or QOS_CONTROL_RE.search(value):
        raise ValueError(f"{label}无效")
    return value


def _safe_slug(value: Any, *, allow_none: bool = False, label: str = "编号") -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not QOS_SLUG_RE.fullmatch(value):
        raise ValueError(f"{label}无效")
    return value


def _literal_unicast(value: Any) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError("IP 必须是 literal unicast 地址")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        raise ValueError("IP 必须是 literal unicast 地址") from None
    if address.is_unspecified or address.is_multicast or address.is_loopback or address.is_reserved:
        raise ValueError("IP 必须是 literal unicast 地址")
    return str(address)


class QoSPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    id: str = Field(min_length=1, max_length=64)
    label: str = Field(min_length=1, max_length=80)
    device_id: str | None = Field(default=None, max_length=64)
    ip: str
    enabled: StrictBool = True
    upload_mbps: float | None = None
    download_mbps: float | None = None
    guaranteed_upload_mbps: float = 0.1
    guaranteed_download_mbps: float = 0.1
    priority: int = 3

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return _safe_slug(value, label="策略编号") or ""

    @field_validator("label")
    @classmethod
    def valid_label(cls, value: str) -> str:
        return _safe_text(value, minimum=1, maximum=80, label="策略标签")

    @field_validator("device_id", mode="before")
    @classmethod
    def valid_device_id(cls, value: Any) -> str | None:
        return _safe_slug(value, allow_none=True, label="设备编号")

    @field_validator("ip")
    @classmethod
    def valid_ip(cls, value: str) -> str:
        return _literal_unicast(value)

    @field_validator("enabled")
    @classmethod
    def valid_enabled(cls, value: Any) -> bool:
        if not isinstance(value, bool):
            raise ValueError("enabled 必须是布尔值")
        return value

    @field_validator("upload_mbps", "download_mbps", mode="before")
    @classmethod
    def valid_max_rate(cls, value: Any) -> float | None:
        return _strict_number(value, minimum=0.001, maximum=100000.0, allow_none=True)

    @field_validator("guaranteed_upload_mbps", "guaranteed_download_mbps", mode="before")
    @classmethod
    def valid_guarantee(cls, value: Any) -> float:
        result = _strict_number(value, minimum=0.001, maximum=100000.0)
        assert result is not None
        return result

    @field_validator("priority", mode="before")
    @classmethod
    def valid_priority(cls, value: Any) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 3, 7):
            raise ValueError("priority 必须是 0、3 或 7")
        return value

    @model_validator(mode="after")
    def valid_policy_rates(self) -> "QoSPolicy":
        for maximum, guarantee in (
            (self.upload_mbps, self.guaranteed_upload_mbps),
            (self.download_mbps, self.guaranteed_download_mbps),
        ):
            if maximum is not None and maximum < guarantee:
                raise ValueError("策略最大速率不能小于保证速率")
        return self


class QoSConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    interface: str = ""
    upload_mbps: float
    download_mbps: float
    policies: list[QoSPolicy] = Field(default_factory=list, max_length=QOS_MAX_POLICIES)

    @field_validator("interface", mode="before")
    @classmethod
    def valid_interface(cls, value: Any) -> str:
        if value is None:
            raise ValueError("接口名无效")
        if not isinstance(value, str):
            raise ValueError("接口名无效")
        value = value.strip()
        if value and not QOS_IFACE_RE.fullmatch(value):
            raise ValueError("接口名无效")
        return value

    @field_validator("upload_mbps", "download_mbps", mode="before")
    @classmethod
    def valid_capacity(cls, value: Any) -> float:
        result = _strict_number(value, minimum=1.0, maximum=100000.0)
        assert result is not None
        return result

    @model_validator(mode="after")
    def validate_policies(self) -> "QoSConfig":
        seen_ips: set[str] = set()
        seen_ids: set[str] = set()
        upload_guarantee = 0.0
        download_guarantee = 0.0
        for policy in self.policies:
            if policy.id in seen_ids:
                raise ValueError("策略编号不能重复")
            seen_ids.add(policy.id)
            if policy.ip in seen_ips:
                raise ValueError("策略 IP 不能重复")
            seen_ips.add(policy.ip)
            if not policy.enabled:
                continue
            upload_max = policy.upload_mbps if policy.upload_mbps is not None else self.upload_mbps
            download_max = policy.download_mbps if policy.download_mbps is not None else self.download_mbps
            if policy.guaranteed_upload_mbps > upload_max or upload_max > self.upload_mbps:
                raise ValueError("启用策略的上传速率必须满足 guarantee <= max <= 总容量")
            if policy.guaranteed_download_mbps > download_max or download_max > self.download_mbps:
                raise ValueError("启用策略的下载速率必须满足 guarantee <= max <= 总容量")
            upload_guarantee += policy.guaranteed_upload_mbps
            download_guarantee += policy.guaranteed_download_mbps
        if upload_guarantee + QOS_DEFAULT_CLASS_Mbps > self.upload_mbps + 1e-9:
            raise ValueError("上传保证速率总和超过容量")
        if download_guarantee + QOS_DEFAULT_CLASS_Mbps > self.download_mbps + 1e-9:
            raise ValueError("下载保证速率总和超过容量")
        return self


class QoSConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    config: QoSConfig

    @field_validator("expected_revision", mode="before")
    @classmethod
    def valid_revision(cls, value: Any) -> int:
        return _strict_revision(value)


class QoSApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int

    @field_validator("expected_revision", mode="before")
    @classmethod
    def valid_revision(cls, value: Any) -> int:
        return _strict_revision(value)


# Short aliases keep the public contract readable for API/front-end adapters.
Policy = QoSPolicy
QoSConfigModel = QoSConfig


def _default_config() -> QoSConfig:
    return QoSConfig(interface="", upload_mbps=1.0, download_mbps=1.0, policies=[])


def _json_config(config: QoSConfig) -> dict[str, Any]:
    return config.model_dump(mode="json")


def _rate(value: float) -> str:
    # Use an integer bit rate rounded down.  This keeps the programmed ceil
    # from exceeding a user supplied decimal Mbps value and preserves the
    # 0.001 Mbps minimum guarantee without a floating-point kbit round-up.
    return f"{max(1, int(math.floor(value * 1_000_000.0)))}bit"


def _handle_without_colon(value: str) -> str:
    return value[:-1] if value.endswith(":") else value


def _qdisc_kind(item: Mapping[str, Any]) -> str:
    return str(item.get("kind") or "").lower()


def _qdisc_handle(item: Mapping[str, Any]) -> str:
    return str(item.get("handle") or "").lower().rstrip(":")


def _qdisc_default(item: Mapping[str, Any]) -> str | None:
    """Return an HTB default class in canonical hexadecimal form."""
    value = item.get("default")
    options = item.get("options")
    if value is None and isinstance(options, Mapping):
        value = options.get("default")
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return format(value, "x")
    if not isinstance(value, str):
        return None
    value = value.strip().lower().rstrip(":")
    if not value:
        return None
    try:
        if value.startswith("0x"):
            return format(int(value, 16), "x")
        if value.isdigit():
            return format(int(value, 10), "x")
    except ValueError:
        return None
    return value


def _is_root_qdisc(item: Mapping[str, Any]) -> bool:
    return bool(item.get("root")) or item.get("parent") in (None, "", "root")


def _result_from(value: Any) -> CommandResult:
    if isinstance(value, CommandResult):
        return value
    return CommandResult(
        int(getattr(value, "returncode", 1)),
        str(getattr(value, "stdout", "") or ""),
        str(getattr(value, "stderr", "") or ""),
    )


def _default_runner(argv: Sequence[str], timeout: float) -> CommandResult:
    try:
        result = subprocess.run(
            list(argv),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        raise QosCommandError("command_timeout") from None
    except OSError:
        raise QosCommandError("command_unavailable") from None
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    stderr = result.stderr if isinstance(result.stderr, str) else ""
    if len(stdout) > QOS_MAX_COMMAND_OUTPUT or len(stderr) > QOS_MAX_COMMAND_OUTPUT:
        raise QosCommandError("command_output_too_large")
    return CommandResult(result.returncode, stdout, stderr)


class QosManager:
    """Persist desired/applied QoS and safely own Linux tc objects."""

    def __init__(
        self,
        state: Any,
        *,
        runner: Callable[[Sequence[str], float], Any] | None = None,
        platform_name: str | None = None,
        env: Mapping[str, str] | None = None,
        command_finder: Callable[[str], str | None] | None = None,
        interface_provider: Callable[[], Sequence[Any]] | None = None,
        privileged: bool | None = None,
    ):
        self.state = state
        self._runner = runner or _default_runner
        self._platform_name = (platform_name or platform_module.system()).lower()
        self._env = dict(os.environ if env is None else env)
        self._command_finder = command_finder or shutil.which
        self._interface_provider = interface_provider or socket.if_nameindex
        self._privileged_override = privileged
        self._lock = threading.RLock()
        self._last_error: str | None = None

    def _run(self, argv: Sequence[str], *, check: bool = True,
             timeout: float = QOS_COMMAND_TIMEOUT) -> CommandResult:
        try:
            result = _result_from(self._runner(tuple(argv), timeout))
        except QosCommandError:
            raise
        except Exception:
            raise QosCommandError("command_failed") from None
        if check and result.returncode != 0:
            # Classify only fixed, non-sensitive kernel/tool diagnostics. The
            # original stderr is never returned to the API or stored.
            diagnostic = result.stderr.lower()
            if any(text in diagnostic for text in
                   ("unknown qdisc", "unknown filter", "operation not supported",
                    "no such file or directory")):
                raise QosCommandError("kernel_feature_missing")
            if "permission denied" in diagnostic or "operation not permitted" in diagnostic:
                raise QosCommandError("permission_denied")
            if "file exists" in diagnostic:
                raise QosCommandError("object_conflict")
            if "cannot find device" in diagnostic:
                raise QosCommandError("interface_not_found")
            raise QosCommandError("command_exit")
        return result

    def _run_json(self, argv: Sequence[str]) -> Any:
        result = self._run(argv)
        if not result.stdout.strip():
            return []
        try:
            payload = json.loads(result.stdout)
        except (TypeError, ValueError):
            raise QosCommandError("invalid_command_json") from None
        if not isinstance(payload, (list, dict)):
            raise QosCommandError("invalid_command_json")
        return payload

    def _try_json(self, argv: Sequence[str]) -> tuple[bool, Any]:
        try:
            result = self._run(argv, check=False)
        except QosCommandError:
            return False, None
        if result.returncode != 0:
            return False, None
        if not result.stdout.strip():
            return True, []
        try:
            payload = json.loads(result.stdout)
        except (TypeError, ValueError):
            return False, None
        return (True, payload) if isinstance(payload, (list, dict)) else (False, None)

    def _command_exists(self, name: str) -> bool:
        try:
            return bool(self._command_finder(name))
        except Exception:
            return False

    def _has_privilege(self) -> bool:
        if self._privileged_override is not None:
            return bool(self._privileged_override)
        if self._platform_name != "linux":
            return False
        try:
            if os.geteuid() == 0:
                return True
        except AttributeError:
            return False
        try:
            for line in Path("/proc/self/status").read_text(encoding="ascii", errors="ignore").splitlines():
                if line.startswith("CapEff:"):
                    value = int(line.split(":", 1)[1].strip(), 16)
                    return bool(value & (1 << 12))  # CAP_NET_ADMIN
        except (OSError, ValueError):
            return False
        return False

    def _interface_names(self) -> list[str]:
        try:
            values = self._interface_provider()
        except Exception:
            return []
        names: list[str] = []
        for item in values:
            name = item[1] if isinstance(item, (tuple, list)) and len(item) >= 2 else item
            if isinstance(name, str) and QOS_IFACE_RE.fullmatch(name):
                names.append(name)
        return sorted(set(names))

    def capabilities(self) -> dict[str, Any]:
        platform_name = self._platform_name
        reason: str | None = None
        available = True
        if platform_name != "linux":
            available = False
            reason = "仅 Linux tc/HTB/IFB 后端可执行"
        elif self._env.get("R_LINK_QOS_ENABLED", "").strip().lower() != "true":
            available = False
            reason = "R_LINK_QOS_ENABLED 未开启"
        elif not self._command_exists("tc") or not self._command_exists("ip"):
            available = False
            reason = "未找到 tc 或 ip"
        elif not self._has_privilege():
            available = False
            reason = "需要 root 或 CAP_NET_ADMIN"
        return {
            "available": available,
            "platform": platform_name,
            "reason": reason,
            "interfaces": [{"name": name} for name in self._interface_names()],
            "backend": QOS_BACKEND,
        }

    def _qos_dir(self, *, create: bool = False) -> Path | None:
        root = Path(getattr(self.state, "root", "."))
        if root.is_symlink() or (root.exists() and not root.is_dir()):
            raise QosCommandError("ownership_root_invalid")
        if root.exists() and stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise QosCommandError("ownership_root_permissions")
        directory = root / "qos"
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            raise QosCommandError("ownership_directory_invalid")
        if directory.exists():
            if not directory.is_dir():
                raise QosCommandError("ownership_directory_invalid")
            mode = stat.S_IMODE(directory.stat().st_mode)
            if mode & 0o077:
                raise QosCommandError("ownership_directory_permissions")
            return directory
        if not create:
            return None
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if stat.S_IMODE(root.stat().st_mode) & 0o077:
            raise QosCommandError("ownership_root_permissions")
        directory.mkdir(mode=0o700)
        return directory

    def _marker_path(self, *, create: bool = False) -> Path | None:
        directory = self._qos_dir(create=create)
        return directory / "ownership.json" if directory else None

    def _validate_marker(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """Validate every value that can later become an argv component.

        The marker is local state, but it is also the authority used by
        cleanup.  Treat malformed or hand-edited state as unowned rather than
        allowing it to select an arbitrary interface, handle, or IFB name.
        """
        if not isinstance(value, Mapping):
            raise QosCommandError("ownership_marker_invalid")
        if value.get("owner") != QOS_OWNER or value.get("version") != QOS_MARKER_VERSION:
            raise QosCommandError("ownership_marker_invalid")
        if value.get("phase") not in {"applying", "active", "cleanup"}:
            raise QosCommandError("ownership_marker_invalid")
        try:
            revision = _strict_revision(value.get("revision"))
        except ValueError:
            raise QosCommandError("ownership_marker_invalid") from None
        interface = value.get("interface")
        if not isinstance(interface, str) or not QOS_IFACE_RE.fullmatch(interface):
            raise QosCommandError("ownership_marker_invalid")
        expected = self._object_names(interface)
        for key in ("ifb", "root_handle", "ifb_handle", "ingress_handle"):
            if value.get(key) != expected[key]:
                raise QosCommandError("ownership_marker_invalid")
        alias = value.get("ifb_alias")
        if not isinstance(alias, str) or not QOS_ALIAS_RE.fullmatch(alias):
            raise QosCommandError("ownership_marker_invalid")
        interface_ifindex = value.get("interface_ifindex")
        if (isinstance(interface_ifindex, bool) or not isinstance(interface_ifindex, int)
                or interface_ifindex <= 0):
            raise QosCommandError("ownership_marker_invalid")
        ifb_ifindex = value.get("ifb_ifindex")
        if ifb_ifindex is not None and (
                isinstance(ifb_ifindex, bool) or not isinstance(ifb_ifindex, int) or ifb_ifindex <= 0):
            raise QosCommandError("ownership_marker_invalid")
        flags = ("ifb_created", "ifb_alias_set", "ifb_qdisc_created", "ingress_created", "root_created")
        if any(type(value.get(flag)) is not bool for flag in flags):
            raise QosCommandError("ownership_marker_invalid")
        if value.get("ifb_created") and ifb_ifindex is None:
            raise QosCommandError("ownership_marker_invalid")
        if value.get("phase") == "active" and not all(value.get(flag) for flag in flags):
            raise QosCommandError("ownership_marker_invalid")
        try:
            config = QoSConfig.model_validate(value.get("config"))
        except Exception:
            raise QosCommandError("ownership_marker_invalid") from None
        if config.interface != interface:
            raise QosCommandError("ownership_marker_invalid")
        # Keep the local variable explicit so static analysis does not treat
        # the revision check above as an unused validation side effect.
        if not isinstance(revision, int):
            raise QosCommandError("ownership_marker_invalid")
        return dict(value)

    def _load_marker(self) -> dict[str, Any] | None:
        path = self._marker_path()
        if path is None:
            return None
        if path.is_symlink():
            raise QosCommandError("ownership_marker_invalid")
        if not path.exists():
            return None
        if not path.is_file():
            raise QosCommandError("ownership_marker_invalid")
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise QosCommandError("ownership_marker_permissions")
        if path.stat().st_size > 64 * 1024:
            raise QosCommandError("ownership_marker_too_large")
        try:
            fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as stream:
                raw = stream.read(64 * 1024 + 1)
            if len(raw) > 64 * 1024:
                raise ValueError()
            value = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeError, ValueError):
            raise QosCommandError("ownership_marker_invalid") from None
        return self._validate_marker(value)

    def _save_marker(self, marker: Mapping[str, Any]) -> None:
        marker = self._validate_marker(marker)
        path = self._marker_path(create=True)
        assert path is not None
        if path.is_symlink():
            raise QosCommandError("ownership_marker_invalid")
        temporary = path.with_name(f".ownership.json.tmp.{os.getpid()}")
        if temporary.exists() or temporary.is_symlink():
            raise QosCommandError("ownership_marker_temp_exists")
        payload = json.dumps(dict(marker), ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(payload) > 64 * 1024:
            raise QosCommandError("ownership_marker_too_large")
        try:
            fd = os.open(str(temporary), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
            os.chmod(path, 0o600)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise QosCommandError("ownership_marker_write_failed") from None

    def _delete_marker(self) -> None:
        path = self._marker_path()
        if path is None:
            return
        if path.is_symlink():
            raise QosCommandError("ownership_marker_invalid")
        if not path.exists():
            return
        try:
            path.unlink()
        except OSError:
            raise QosCommandError("ownership_marker_delete_failed") from None

    def _desired(self) -> tuple[int, QoSConfig]:
        records = self.state.list(QOS_CONFIG_KIND)
        item = next((value for value in records if value.get("id") == QOS_RECORD_ID), None)
        if not item:
            return 0, _default_config()
        try:
            revision = _strict_revision(item.get("revision", 0))
            config = QoSConfig.model_validate(item.get("config", {}))
        except Exception:
            raise QosCommandError("desired_config_invalid") from None
        return revision, config

    def _applied(self) -> tuple[int, QoSConfig] | None:
        records = self.state.list(QOS_APPLIED_KIND)
        item = next((value for value in records if value.get("id") == QOS_RECORD_ID), None)
        if not item:
            return None
        try:
            revision = _strict_revision(item.get("revision"))
            config = QoSConfig.model_validate(item.get("config", {}))
        except Exception:
            raise QosCommandError("applied_config_invalid") from None
        return revision, config

    @staticmethod
    def _marker_matches_applied(marker: Mapping[str, Any], applied: tuple[int, QoSConfig]) -> bool:
        """Require the persisted kernel marker and applied record to agree."""
        if marker.get("revision") != applied[0]:
            return False
        try:
            return QoSConfig.model_validate(marker.get("config")) == applied[1]
        except Exception:
            return False

    def _save_desired(self, revision: int, config: QoSConfig) -> None:
        self.state.save(QOS_CONFIG_KIND, {"revision": revision, "config": _json_config(config)}, QOS_RECORD_ID)

    def _save_applied(self, revision: int, config: QoSConfig) -> None:
        self.state.save(QOS_APPLIED_KIND, {"revision": revision, "config": _json_config(config)}, QOS_RECORD_ID)

    def _delete_applied(self) -> None:
        self.state.delete(QOS_APPLIED_KIND, QOS_RECORD_ID)

    def _source_hash(self, interface: str) -> str:
        return hashlib.sha256(f"{QOS_OWNER}\0{interface}".encode("utf-8")).hexdigest()[:10]

    def _object_names(self, interface: str) -> dict[str, str]:
        digest = self._source_hash(interface)
        return {
            "ifb": "rlq" + digest,
            "root_handle": "c" + digest[:3] + ":",
            "ifb_handle": "d" + digest[:3] + ":",
            "ingress_handle": "ffff:",
        }

    def _find_root(self, payload: Any) -> Mapping[str, Any] | None:
        items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        for item in items:
            if isinstance(item, Mapping) and _is_root_qdisc(item):
                return item
        return None

    def _qdiscs(self, interface: str) -> list[Mapping[str, Any]]:
        payload = self._run_json(["tc", "-j", "qdisc", "show", "dev", interface])
        items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        return [item for item in items if isinstance(item, Mapping)]

    def _classes(self, interface: str) -> list[Mapping[str, Any]]:
        payload = self._run_json(["tc", "-j", "class", "show", "dev", interface])
        items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        return [item for item in items if isinstance(item, Mapping)]

    def _filters(self, interface: str, parent: str | None = None) -> list[Mapping[str, Any]]:
        argv = ["tc", "-j", "filter", "show", "dev", interface]
        if parent:
            argv += ["parent", parent]
        payload = self._run_json(argv)
        items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        return [item for item in items if isinstance(item, Mapping)]

    def _link(self, name: str) -> Mapping[str, Any] | None:
        ok, payload = self._try_json(["ip", "-j", "-d", "link", "show", "dev", name])
        if not ok:
            return None
        items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        return items[0] if items and isinstance(items[0], Mapping) else None

    def _link_index(self, item: Mapping[str, Any] | None) -> int | None:
        if item is None:
            return None
        value = item.get("ifindex")
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            return None
        return value

    def _link_alias(self, item: Mapping[str, Any] | None) -> str | None:
        if item is None:
            return None
        value = item.get("ifalias")
        if isinstance(value, str):
            return value
        # Keep compatibility with iproute2 JSON variants without accepting
        # arbitrary nested text as an ownership proof.
        value = item.get("alias")
        return value if isinstance(value, str) else None

    def _link_is_ifb(self, item: Mapping[str, Any]) -> bool:
        linkinfo = item.get("linkinfo")
        if isinstance(linkinfo, Mapping) and linkinfo.get("info_kind") == "ifb":
            return True
        return item.get("link_type") == "ifb" or item.get("kind") == "ifb"

    @staticmethod
    def _link_is_up(item: Mapping[str, Any]) -> bool:
        """Accept the two iproute2 JSON representations of link state."""
        state = item.get("operstate")
        if isinstance(state, str) and state.upper() == "UP":
            return True
        flags = item.get("flags")
        return isinstance(flags, list) and any(
            isinstance(flag, str) and flag.upper() == "UP" for flag in flags
        )

    def _preflight(self, config: QoSConfig, *, ignore_marker: bool = False) -> None:
        if not config.interface:
            raise QosCommandError("interface_required")
        if config.interface not in self._interface_names():
            raise QosCommandError("interface_not_found")
        objects = self._object_names(config.interface)
        marker = self._load_marker()
        if marker is not None and not ignore_marker:
            if marker.get("interface") != config.interface:
                raise QosCommandError("ownership_interface_conflict")
            return
        root = self._find_root(self._qdiscs(config.interface))
        if root is not None:
            kind = _qdisc_kind(root)
            handle = _qdisc_handle(root)
            if handle not in {"0", ""}:
                raise QosCommandError("root_qdisc_conflict")
            # A handle-0 system default is safe to replace only when it has no
            # class/filter state that would be lost with the service qdisc.
            if self._classes(config.interface):
                raise QosCommandError("root_qdisc_conflict")
        if self._filters(config.interface):
            raise QosCommandError("interface_filter_conflict")
        qdiscs = self._qdiscs(config.interface)
        if any(_qdisc_kind(item) in {"ingress", "clsact"} for item in qdiscs):
            raise QosCommandError("ingress_qdisc_conflict")
        # A handle-0 default is replaceable only when it is a completely
        # empty graph.  Reject child qdiscs before creating an IFB or ingress
        # qdisc so a failed race cannot leave a partial service graph behind.
        if not self._qdisc_set_ok(
                config.interface, qdiscs, root_handle=objects["root_handle"],
                root_created=False, ingress_handle=objects["ingress_handle"],
                ingress_created=False):
            raise QosCommandError("root_qdisc_conflict")
        if self._link(objects["ifb"]) is not None:
            raise QosCommandError("ifb_name_conflict")

    def _baseline_marker(self, config: QoSConfig, revision: int) -> dict[str, Any]:
        objects = self._object_names(config.interface)
        return {
            "owner": QOS_OWNER,
            "version": QOS_MARKER_VERSION,
            "phase": "applying",
            "revision": revision,
            "interface": config.interface,
            "ifb": objects["ifb"],
            "ifb_alias": "r-link-qos-" + secrets.token_hex(16),
            "interface_ifindex": None,
            "ifb_ifindex": None,
            "ifb_alias_set": False,
            "root_handle": objects["root_handle"],
            "ifb_handle": objects["ifb_handle"],
            "ingress_handle": objects["ingress_handle"],
            "ifb_created": False,
            "ifb_qdisc_created": False,
            "ingress_created": False,
            "root_created": False,
            "config": _json_config(config),
        }

    def _class_commands(self, device: str, parent: str, root_handle: str,
                        capacity: float, direction: str, policies: Sequence[QoSPolicy]) -> list[list[str]]:
        root_class = root_handle + "1"
        default_class = root_handle + "ffff"
        commands: list[list[str]] = [
            # This is the first creation of a service-owned root qdisc.  `add`
            # makes a preflight/install race fail closed if another actor has
            # installed a root qdisc in the meantime; it never overwrites it.
            ["tc", "qdisc", "add", "dev", device, "root", "handle", root_handle,
             "htb", "default", "ffff"],
            ["tc", "class", "replace", "dev", device, "parent", root_handle,
             "classid", root_class, "htb", "rate", _rate(capacity), "ceil", _rate(capacity)],
            ["tc", "class", "replace", "dev", device, "parent", root_class,
             "classid", default_class, "htb", "rate", QOS_DEFAULT_CLASS_RATE,
             "ceil", _rate(capacity), "prio", "7"],
        ]
        for index, policy in enumerate(policies):
            if not policy.enabled:
                continue
            guarantee = policy.guaranteed_upload_mbps if direction == "upload" else policy.guaranteed_download_mbps
            maximum = policy.upload_mbps if direction == "upload" else policy.download_mbps
            maximum = capacity if maximum is None else maximum
            classid = root_handle + format(10 + index, "x")
            commands.append([
                "tc", "class", "replace", "dev", device, "parent", root_class,
                "classid", classid, "htb", "rate", _rate(guarantee),
                "ceil", _rate(maximum), "prio", str(policy.priority),
            ])
        return commands

    def _filter_command(self, device: str, parent: str, policy: QoSPolicy,
                        index: int, *, destination: bool, class_handle: str) -> list[str]:
        version = ipaddress.ip_address(policy.ip).version
        protocol = "ip" if version == 4 else "ipv6"
        selector = "dst" if destination else "src"
        bits = "32" if version == 4 else "128"
        return [
            "tc", "filter", "replace", "dev", device, "parent", parent,
            "protocol", protocol, "pref", str(100 + index), "flower",
            f"{selector}_ip", f"{policy.ip}/{bits}", "classid", class_handle,
        ]

    def _build_install_commands(self, config: QoSConfig, marker: Mapping[str, Any]) -> list[list[str]]:
        interface = config.interface
        ifb = str(marker["ifb"])
        root_handle = str(marker["root_handle"])
        ifb_handle = str(marker["ifb_handle"])
        commands: list[list[str]] = [
            ["ip", "link", "add", "name", ifb, "type", "ifb"],
            ["ip", "link", "set", "dev", ifb, "alias", str(marker["ifb_alias"])],
            ["ip", "link", "set", "dev", ifb, "up"],
        ]
        commands += self._class_commands(ifb, ifb_handle, ifb_handle, config.upload_mbps, "upload", config.policies)
        for index, policy in enumerate(config.policies):
            if not policy.enabled:
                continue
            commands.append(self._filter_command(ifb, ifb_handle, policy, index,
                                                 destination=False, class_handle=ifb_handle + format(10 + index, "x")))
        commands += [
            ["tc", "qdisc", "add", "dev", interface, "ingress", "handle", str(marker["ingress_handle"])],
        ]
        for index, policy in enumerate(config.policies):
            if not policy.enabled:
                continue
            version = ipaddress.ip_address(policy.ip).version
            protocol = "ip" if version == 4 else "ipv6"
            selector = "src"
            bits = "32" if version == 4 else "128"
            commands.append([
                "tc", "filter", "replace", "dev", interface, "parent", str(marker["ingress_handle"]),
                "protocol", protocol, "pref", str(100 + index), "flower", f"{selector}_ip",
                f"{policy.ip}/{bits}", "action", "mirred", "egress", "redirect", "dev", ifb,
            ])
        # Redirect IPv4 and IPv6 packets separately.  ARP remains on the
        # physical interface; IPv6 neighbor discovery is IPv6 traffic and is
        # therefore reinjected through the IFB path with the other IPv6 data.
        for protocol, preference in (("ip", "32000"), ("ipv6", "32001")):
            commands.append([
                "tc", "filter", "replace", "dev", interface, "parent", str(marker["ingress_handle"]),
                "protocol", protocol, "pref", preference, "matchall", "action", "mirred",
                "egress", "redirect", "dev", ifb,
            ])
        commands += self._class_commands(interface, root_handle, root_handle,
                                         config.download_mbps, "download", config.policies)
        for index, policy in enumerate(config.policies):
            if not policy.enabled:
                continue
            commands.append(self._filter_command(interface, root_handle, policy, index,
                                                 destination=True, class_handle=root_handle + format(10 + index, "x")))
        return commands

    def plan(self, config: QoSConfig | Mapping[str, Any]) -> list[list[str]]:
        """Return the exact safe argv plan without executing it."""
        parsed = config if isinstance(config, QoSConfig) else QoSConfig.model_validate(config)
        if not parsed.interface:
            raise HTTPException(422, "apply 前必须选择 Linux 接口")
        return self._build_install_commands(parsed, self._baseline_marker(parsed, 0))

    def _save_marker_flags(self, marker: dict[str, Any], **flags: Any) -> dict[str, Any]:
        marker.update(flags)
        self._save_marker(marker)
        return marker

    def _matches_qdisc(self, qdiscs: Sequence[Mapping[str, Any]], *, kind: str, handle: str,
                       default: str | None = None, root: bool | None = None) -> bool:
        expected = _handle_without_colon(handle)
        expected_default = None if default is None else _handle_without_colon(default).lower()
        return any(
            _qdisc_kind(item) == kind
            and _qdisc_handle(item) == expected
            and (expected_default is None or _qdisc_default(item) == expected_default)
            and (root is None or bool(item.get("root")) is root)
            for item in qdiscs
        )

    def _qdisc_set_ok(self, device: str, qdiscs: Sequence[Mapping[str, Any]], *,
                      root_handle: str, root_created: bool,
                      ingress_handle: str | None = None,
                      ingress_created: bool = False,
                      expected_default: str | None = None) -> bool:
        """Validate the complete qdisc graph before claiming ownership.

        tc permits child qdiscs to coexist with a service root.  A child is
        nevertheless part of the operator's graph, so silently deleting the
        root could also delete or disrupt an unrelated qdisc.  Only the
        service root plus its own ingress qdisc are accepted here.  When a
        checkpoint says the root is already absent, the ordinary handle-0
        empty default is the sole safe baseline.
        """
        items = [item for item in qdiscs if isinstance(item, Mapping)]
        roots = [item for item in items if _is_root_qdisc(item)]
        ingress = [item for item in items if _qdisc_kind(item) in {"ingress", "clsact"}]
        known = {id(item) for item in roots + ingress}
        if len(roots) > 1 or len(ingress) > 1 or any(id(item) not in known for item in items):
            return False

        if ingress_created:
            if ingress_handle is None or len(ingress) != 1:
                return False
            if (_qdisc_kind(ingress[0]) != "ingress"
                    or _qdisc_handle(ingress[0]) != _handle_without_colon(ingress_handle)):
                return False
        elif ingress:
            return False

        if root_created:
            if len(roots) != 1:
                return False
            root = roots[0]
            if (_qdisc_kind(root) != "htb"
                    or _qdisc_handle(root) != _handle_without_colon(root_handle)):
                return False
            if expected_default is not None and _qdisc_default(root) != _handle_without_colon(expected_default).lower():
                return False
        elif roots:
            root = roots[0]
            if _qdisc_handle(root) not in {"0", ""}:
                return False
            # A handle-0 root with state beneath it is not a safe empty
            # baseline.  Do not claim that it is ours during cleanup.
            if self._classes(device) or self._filters(device):
                return False
        return True

    @staticmethod
    def _normal_id(value: Any) -> str | None:
        if not isinstance(value, str) or not value:
            return None
        return value.lower().rstrip(":")

    @staticmethod
    def _class_id(item: Mapping[str, Any]) -> str | None:
        return QosManager._normal_id(item.get("classid") or item.get("handle"))

    @staticmethod
    def _class_kind(item: Mapping[str, Any]) -> str:
        # iproute2 versions use either `class` or `kind` in JSON output.
        return str(item.get("class") or item.get("kind") or "").lower()

    @staticmethod
    def _class_options(item: Mapping[str, Any]) -> Mapping[str, Any]:
        options = item.get("options")
        if not isinstance(options, Mapping):
            return item
        # Some iproute2 versions put rate/ceil/prio at the top level while
        # still emitting an options object. Merge both representations.
        merged = dict(item)
        merged.update(options)
        return merged

    @staticmethod
    def _class_parent(item: Mapping[str, Any]) -> str | None:
        value = item.get("parent")
        if not isinstance(value, str) or not value:
            return None
        return value.lower().rstrip(":")

    @classmethod
    def _class_parent_matches(cls, item: Mapping[str, Any], expected: str, *, root: bool = False) -> bool:
        if root and item.get("root") is True:
            return True
        if not root and item.get("root") is True:
            return False
        if "parent" not in item:
            return False
        actual = cls._class_parent(item)
        if actual is None:
            return False
        if root:
            return actual in {"root", cls._normal_id(expected)}
        return actual == cls._normal_id(expected)

    @staticmethod
    def _tc_rate_bytes(value: Any) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)) and math.isfinite(float(value)) and value >= 0:
            return float(value)
        if isinstance(value, Mapping):
            for key in ("bytes_per_second", "bytes", "value"):
                result = QosManager._tc_rate_bytes(value.get(key))
                if result is not None:
                    return result
            return None
        if isinstance(value, str):
            match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([kmgt]?bit)?\s*", value.lower())
            if not match:
                return None
            number = float(match.group(1))
            unit = match.group(2) or "bit"
            multiplier = {"bit": 1.0, "kbit": 1000.0, "mbit": 1_000_000.0,
                          "gbit": 1_000_000_000.0, "tbit": 1_000_000_000_000.0}[unit]
            return number * multiplier / 8.0
        return None

    @classmethod
    def _rate_matches(cls, value: Any, megabits: float) -> bool:
        actual = cls._tc_rate_bytes(value)
        if actual is None:
            return False
        expected = megabits * 1_000_000.0 / 8.0
        return abs(actual - expected) <= 1.0

    def _verify_classes(self, device: str, config: QoSConfig, *, direction: str,
                        root_handle: str) -> bool:
        items = self._classes(device)
        specs: dict[str, tuple[float, float, int | None]] = {
            self._normal_id(root_handle + "1") or "": (
                config.upload_mbps if direction == "upload" else config.download_mbps,
                config.upload_mbps if direction == "upload" else config.download_mbps,
                None,
            ),
            self._normal_id(root_handle + "ffff") or "": (
                QOS_DEFAULT_CLASS_Mbps,
                config.upload_mbps if direction == "upload" else config.download_mbps,
                7,
            ),
        }
        for index, policy in enumerate(config.policies):
            if not policy.enabled:
                continue
            guarantee = policy.guaranteed_upload_mbps if direction == "upload" else policy.guaranteed_download_mbps
            maximum = policy.upload_mbps if direction == "upload" else policy.download_mbps
            maximum = (config.upload_mbps if direction == "upload" else config.download_mbps) if maximum is None else maximum
            specs[self._normal_id(root_handle + format(10 + index, "x")) or ""] = (guarantee, maximum, policy.priority)
        if len(items) != len(specs):
            return False
        for item in items:
            if self._class_kind(item) != "htb":
                return False
            class_id = self._class_id(item)
            if class_id not in specs:
                return False
            rate, ceil, priority = specs[class_id]
            if class_id == self._normal_id(root_handle + "1"):
                if not self._class_parent_matches(item, root_handle, root=True):
                    return False
            elif not self._class_parent_matches(item, root_handle + "1"):
                return False
            options = self._class_options(item)
            if not self._rate_matches(options.get("rate"), rate) or not self._rate_matches(options.get("ceil"), ceil):
                return False
            if priority is not None:
                value = options.get("prio", item.get("prio"))
                if isinstance(value, bool) or not isinstance(value, int) or value != priority:
                    return False
        return True

    @staticmethod
    def _filter_options(item: Mapping[str, Any]) -> Mapping[str, Any]:
        options = item.get("options")
        return options if isinstance(options, Mapping) else item

    @classmethod
    def _filter_keys(cls, item: Mapping[str, Any]) -> Mapping[str, Any] | None:
        keys = cls._filter_options(item).get("keys")
        return keys if isinstance(keys, Mapping) else None

    @classmethod
    def _filter_detail_items(cls, items: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Drop iproute2's summary/header row for each filter.

        Recent tc JSON emits a short ``protocol/pref/kind/chain`` row followed
        by a detail row with ``options``.  Treating both as filters would
        double the expected count and could make a header look like a valid
        rule.  A detail row must carry options or one of the legacy flattened
        rule fields; a header is never considered sufficient evidence of
        ownership.
        """
        details: list[Mapping[str, Any]] = []
        for item in items:
            if not isinstance(item, Mapping):
                continue
            options = item.get("options")
            if isinstance(options, Mapping):
                details.append(item)
                continue
            if any(key in item for key in ("keys", "actions", "classid", "flowid",
                                            "src_ip", "dst_ip")):
                details.append(item)
        return details

    @classmethod
    def _filter_value(cls, item: Mapping[str, Any], key: str) -> Any:
        options = cls._filter_options(item)
        value = options.get(key)
        if value is not None:
            return value
        keys = options.get("keys")
        if isinstance(keys, Mapping):
            return keys.get(key)
        return None

    @classmethod
    def _filter_pref(cls, item: Mapping[str, Any]) -> int | None:
        value = item.get("pref")
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _filter_ip(cls, item: Mapping[str, Any], selector: str) -> str | None:
        value = cls._filter_value(item, selector + "_ip")
        if not isinstance(value, str):
            return None
        try:
            address = ipaddress.ip_interface(value).ip
            network = ipaddress.ip_network(value, strict=False)
            if network.prefixlen != address.max_prefixlen:
                return None
            return network.with_prefixlen
        except ValueError:
            return None

    @classmethod
    def _filter_classid(cls, item: Mapping[str, Any]) -> str | None:
        options = cls._filter_options(item)
        return cls._normal_id(options.get("classid") or options.get("flowid") or item.get("classid"))

    @staticmethod
    def _filter_chain(item: Mapping[str, Any]) -> int | None:
        value = item.get("chain", 0)
        if isinstance(value, bool):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _redirect_device(cls, item: Mapping[str, Any]) -> str | None:
        options = cls._filter_options(item)
        if "actions" in options:
            actions = options.get("actions")
        else:
            actions = item.get("actions")
        if isinstance(actions, Mapping):
            actions = [actions]
        # A service-owned redirect has exactly one action.  Refuse an
        # unexpected action chain rather than treating the first redirect as
        # proof that the rule still has the intended behavior.
        if not isinstance(actions, list) or len(actions) != 1:
            return None
        action = actions[0]
        if not isinstance(action, Mapping):
            return None
        kind = str(action.get("kind") or action.get("action") or "").lower()
        effect = str(action.get("mirred_action") or action.get("eaction") or action.get("action") or "").lower()
        if kind != "mirred" or effect != "redirect":
            return None
        direction = action.get("direction")
        if direction is not None and str(direction).lower() != "egress":
            return None
        control = action.get("control_action")
        if control is not None and (
                not isinstance(control, Mapping)
                or str(control.get("type") or "").lower() != "stolen"):
            return None
        device = action.get("to_dev") or action.get("ifname") or action.get("dev")
        return device if isinstance(device, str) else None

    @classmethod
    def _filter_has_actions(cls, item: Mapping[str, Any]) -> bool:
        """Distinguish an absent action chain from an invalid one.

        ``_redirect_device`` intentionally returns ``None`` for both cases;
        callers verifying a rule which should have no action must still reject
        an unexpected mirror, sample, or malformed action chain.
        """
        options = cls._filter_options(item)
        if "actions" in options:
            actions = options.get("actions")
        elif "actions" in item:
            actions = item.get("actions")
        else:
            return False
        if actions is None:
            return False
        if isinstance(actions, list):
            return bool(actions)
        return True

    def _verify_filter_set(self, device: str, parent: str,
                           expected: Sequence[Mapping[str, Any]]) -> bool:
        items = self._filter_detail_items(self._filters(device, parent))
        if len(items) != len(expected):
            return False
        used: set[int] = set()
        for wanted in expected:
            matched = False
            for index, item in enumerate(items):
                if index in used:
                    continue
                if self._filter_pref(item) != wanted.get("pref"):
                    continue
                if self._filter_chain(item) != 0:
                    continue
                if str(item.get("protocol") or "").lower() != wanted.get("protocol"):
                    continue
                if str(item.get("kind") or "").lower() != wanted.get("kind"):
                    continue
                selector = wanted.get("selector")
                keys = self._filter_keys(item)
                if selector:
                    protocol = wanted.get("protocol")
                    expected_eth_type = "ipv4" if protocol == "ip" else "ipv6" if protocol == "ipv6" else None
                    if expected_eth_type is None or keys is None:
                        continue
                    if set(keys) != {"eth_type", str(selector) + "_ip"}:
                        continue
                    if keys.get("eth_type") != expected_eth_type:
                        continue
                elif keys not in (None, {}):
                    continue
                if selector and self._filter_ip(item, str(selector)) != wanted.get("ip"):
                    continue
                if wanted.get("classid") != self._filter_classid(item):
                    continue
                expected_redirect = wanted.get("redirect")
                if expected_redirect is None:
                    if self._filter_has_actions(item):
                        continue
                elif expected_redirect != self._redirect_device(item):
                    continue
                used.add(index)
                matched = True
                break
            if not matched:
                return False
        return True

    def _verify_class_ids(self, device: str, config: QoSConfig, *, root_handle: str) -> bool:
        expected = {
            self._normal_id(root_handle + "1"),
            self._normal_id(root_handle + "ffff"),
        }
        expected.update(
            self._normal_id(root_handle + format(10 + index, "x"))
            for index, policy in enumerate(config.policies) if policy.enabled
        )
        items = self._classes(device)
        actual: set[str | None] = set()
        root_class = self._normal_id(root_handle + "1")
        for item in items:
            if self._class_kind(item) != "htb":
                return False
            class_id = self._class_id(item)
            if class_id == root_class:
                if not self._class_parent_matches(item, root_handle, root=True):
                    return False
            elif not self._class_parent_matches(item, root_handle + "1"):
                return False
            actual.add(class_id)
        return len(items) == len(expected) and actual == expected

    def _expected_filters(self, config: QoSConfig, marker: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        root = str(marker["root_handle"])
        ifb = str(marker["ifb_handle"])
        ifb_name = str(marker["ifb"])
        physical: list[dict[str, Any]] = []
        upload: list[dict[str, Any]] = []
        ingress: list[dict[str, Any]] = []
        for index, policy in enumerate(config.policies):
            if not policy.enabled:
                continue
            address = ipaddress.ip_address(policy.ip)
            protocol = "ip" if address.version == 4 else "ipv6"
            prefix = f"{policy.ip}/{address.max_prefixlen}"
            class_suffix = format(10 + index, "x")
            physical.append({"pref": 100 + index, "protocol": protocol, "kind": "flower",
                             "selector": "dst", "ip": prefix,
                             "classid": self._normal_id(root + class_suffix), "redirect": None})
            upload.append({"pref": 100 + index, "protocol": protocol, "kind": "flower",
                           "selector": "src", "ip": prefix,
                           "classid": self._normal_id(ifb + class_suffix), "redirect": None})
            ingress.append({"pref": 100 + index, "protocol": protocol, "kind": "flower",
                            "selector": "src", "ip": prefix, "classid": None,
                            "redirect": ifb_name})
        for protocol, pref in (("ip", 32000), ("ipv6", 32001)):
            ingress.append({"pref": pref, "protocol": protocol, "kind": "matchall",
                            "selector": None, "ip": None, "classid": None,
                            "redirect": ifb_name})
        return physical, upload, ingress

    def _verify_installed(self, marker: Mapping[str, Any]) -> bool:
        if not all(marker.get(flag) is True for flag in
                   ("ifb_created", "ifb_alias_set", "ifb_qdisc_created", "ingress_created", "root_created")):
            return False
        interface = str(marker["interface"])
        ifb = str(marker["ifb"])
        root_handle = str(marker["root_handle"])
        ifb_handle = str(marker["ifb_handle"])
        interface_link = self._link(interface)
        if self._link_index(interface_link) != marker.get("interface_ifindex"):
            return False
        interface_qdiscs = self._qdiscs(interface)
        if not self._qdisc_set_ok(
                interface, interface_qdiscs, root_handle=root_handle, root_created=True,
                ingress_handle=str(marker["ingress_handle"]), ingress_created=True,
                expected_default="ffff"):
            return False
        ifb_link = self._link(ifb)
        if self._link_index(ifb_link) != marker.get("ifb_ifindex"):
            return False
        if self._link_alias(ifb_link) != marker.get("ifb_alias"):
            return False
        if not self._link_is_ifb(ifb_link or {}):
            return False
        if not self._link_is_up(ifb_link or {}):
            return False
        if not self._qdisc_set_ok(
                ifb, self._qdiscs(ifb), root_handle=ifb_handle, root_created=True,
                expected_default="ffff"):
            return False
        try:
            config = QoSConfig.model_validate(marker["config"])
        except Exception:
            return False
        if not self._verify_classes(interface, config, direction="download", root_handle=root_handle):
            return False
        if not self._verify_classes(ifb, config, direction="upload", root_handle=ifb_handle):
            return False
        physical_filters, upload_filters, ingress_filters = self._expected_filters(config, marker)
        if not self._verify_filter_set(interface, root_handle, physical_filters):
            return False
        if not self._verify_filter_set(ifb, ifb_handle, upload_filters):
            return False
        if not self._verify_filter_set(interface, str(marker["ingress_handle"]), ingress_filters):
            return False
        return True

    def _remove_owned(self, marker: Mapping[str, Any], *, delete_marker: bool = True) -> None:
        if marker.get("owner") != QOS_OWNER or marker.get("version") != QOS_MARKER_VERSION:
            raise QosCommandError("ownership_marker_invalid")
        if marker.get("phase") == "active" and not all(
            marker.get(flag) is True for flag in
            ("ifb_created", "ifb_alias_set", "ifb_qdisc_created", "ingress_created", "root_created")
        ):
            raise QosCommandError("ownership_marker_invalid")
        interface = str(marker.get("interface") or "")
        ifb = str(marker.get("ifb") or "")
        root_handle = str(marker.get("root_handle") or "")
        ifb_handle = str(marker.get("ifb_handle") or "")
        if not QOS_IFACE_RE.fullmatch(interface) or not QOS_IFACE_RE.fullmatch(ifb):
            raise QosCommandError("ownership_marker_invalid")
        if self._link_index(self._link(interface)) != marker.get("interface_ifindex"):
            raise QosCommandError("root_qdisc_ownership_lost")

        # Cleanup is checkpointed before the first destructive command.  A
        # process may die after removing the root qdisc but before removing
        # ingress/IFB; on retry, a handle-0 empty system default is evidence
        # that our root is already gone, never permission to delete it.
        changed = False
        interface_qdiscs = self._qdiscs(interface)
        # A false checkpoint flag is not permission to discover and delete a
        # same-named object.  During an interrupted apply, a marker write may
        # have failed after tc/ip succeeded; keep the marker for an operator
        # instead of guessing that the object is ours.
        if not marker.get("root_created") and not self._qdisc_set_ok(
                interface, interface_qdiscs, root_handle=root_handle, root_created=False,
                ingress_handle=str(marker["ingress_handle"]),
                ingress_created=bool(marker.get("ingress_created"))):
            raise QosCommandError("ownership_unconfirmed")
        if not marker.get("ingress_created") and any(
                _qdisc_kind(item) in {"ingress", "clsact"} for item in interface_qdiscs):
            raise QosCommandError("ownership_unconfirmed")
        if not marker.get("ifb_created") and self._link(ifb) is not None:
            raise QosCommandError("ownership_unconfirmed")
        if marker.get("root_created"):
            existing = self._find_root(interface_qdiscs)
            if existing is None:
                marker["root_created"] = False
                changed = True
            elif (
                _qdisc_handle(existing) in {"0", ""}
                and not self._classes(interface)
                and not self._filters(interface)
            ):
                marker["root_created"] = False
                changed = True
            elif not (
                _qdisc_kind(existing) == "htb" and _qdisc_handle(existing) == _handle_without_colon(root_handle)
            ):
                raise QosCommandError("root_qdisc_ownership_lost")
        if marker.get("ingress_created"):
            existing = next((item for item in interface_qdiscs if _qdisc_kind(item) in {"ingress", "clsact"}), None)
            if existing is None:
                marker["ingress_created"] = False
                changed = True
            elif not (
                _qdisc_kind(existing) == "ingress" and _qdisc_handle(existing) == "ffff"
            ):
                raise QosCommandError("ingress_qdisc_ownership_lost")
        if marker.get("ifb_created"):
            link = self._link(ifb)
            if link is None:
                marker.update({"ifb_created": False, "ifb_alias_set": False,
                               "ifb_qdisc_created": False, "ifb_ifindex": None})
                changed = True
            elif self._link_index(link) != marker.get("ifb_ifindex"):
                raise QosCommandError("ifb_ownership_lost")
            elif not self._link_is_ifb(link):
                raise QosCommandError("ifb_ownership_lost")
            else:
                alias = self._link_alias(link)
                if marker.get("ifb_alias_set") and alias != marker.get("ifb_alias"):
                    raise QosCommandError("ifb_ownership_lost")
                if not marker.get("ifb_alias_set") and alias not in {None, "", marker.get("ifb_alias")}:
                    raise QosCommandError("ifb_ownership_lost")
                if marker.get("ifb_qdisc_created"):
                    if self._matches_qdisc(self._qdiscs(ifb), kind="htb", handle=ifb_handle, root=True):
                        pass
                    elif self._find_root(self._qdiscs(ifb)) is None or (
                            _qdisc_handle(self._find_root(self._qdiscs(ifb)) or {}) in {"0", ""}
                            and not self._classes(ifb)
                            and not self._filters(ifb)):
                        marker["ifb_qdisc_created"] = False
                        changed = True
                    else:
                        raise QosCommandError("ifb_qdisc_ownership_lost")
                elif not self._qdisc_set_ok(
                        ifb, self._qdiscs(ifb), root_handle=ifb_handle, root_created=False):
                    raise QosCommandError("ownership_unconfirmed")

                if not self._qdisc_set_ok(
                        ifb, self._qdiscs(ifb), root_handle=ifb_handle,
                        root_created=bool(marker.get("ifb_qdisc_created"))):
                    raise QosCommandError(
                        "ifb_qdisc_ownership_lost" if marker.get("ifb_qdisc_created")
                        else "ownership_unconfirmed"
                    )

        if not self._qdisc_set_ok(
                interface, interface_qdiscs, root_handle=root_handle,
                root_created=bool(marker.get("root_created")),
                ingress_handle=str(marker["ingress_handle"]),
                ingress_created=bool(marker.get("ingress_created"))):
            raise QosCommandError(
                "root_qdisc_ownership_lost" if marker.get("root_created")
                else "ownership_unconfirmed"
            )

        if marker.get("phase") in {"active", "cleanup"}:
            # Validate every graph component that still exists, including on
            # a cleanup retry.  A foreign class/filter inserted after the
            # checkpoint must stop cleanup before any further deletion.
            try:
                config = QoSConfig.model_validate(marker.get("config"))
            except Exception:
                raise QosCommandError("ownership_marker_invalid") from None
            physical_filters, upload_filters, ingress_filters = self._expected_filters(config, marker)
            if marker.get("root_created") and (
                    not self._verify_class_ids(interface, config, root_handle=root_handle)
                    or not self._verify_filter_set(interface, root_handle, physical_filters)):
                raise QosCommandError("root_qdisc_ownership_lost")
            if marker.get("ifb_qdisc_created") and (
                    not self._verify_class_ids(ifb, config, root_handle=ifb_handle)
                    or not self._verify_filter_set(ifb, ifb_handle, upload_filters)):
                raise QosCommandError("ifb_qdisc_ownership_lost")
            if marker.get("ingress_created") and not self._verify_filter_set(
                    interface, str(marker["ingress_handle"]), ingress_filters):
                raise QosCommandError("ingress_qdisc_ownership_lost")

        if marker.get("phase") != "cleanup":
            marker["phase"] = "cleanup"
            changed = True
        if changed:
            self._save_marker(marker)
        # Delete only after all ownership checks pass.
        if marker.get("root_created"):
            if self._find_root(self._qdiscs(interface)) is not None:
                self._run(["tc", "qdisc", "del", "dev", interface,
                           "handle", root_handle, "root"])
            marker = self._save_marker_flags(marker, root_created=False)
        if marker.get("ingress_created"):
            qdiscs = self._qdiscs(interface)
            if any(_qdisc_kind(item) == "ingress" and _qdisc_handle(item) == "ffff" for item in qdiscs):
                self._run(["tc", "qdisc", "del", "dev", interface, "ingress"])
            marker = self._save_marker_flags(marker, ingress_created=False)
        if marker.get("ifb_created"):
            link = self._link(ifb)
            if link is not None:
                if marker.get("ifb_qdisc_created") and self._matches_qdisc(
                        self._qdiscs(ifb), kind="htb", handle=ifb_handle, root=True):
                    self._run(["tc", "qdisc", "del", "dev", ifb,
                               "handle", ifb_handle, "root"])
                    marker = self._save_marker_flags(marker, ifb_qdisc_created=False)
                self._run(["ip", "link", "del", "dev", ifb])
            marker = self._save_marker_flags(
                marker, ifb_created=False, ifb_alias_set=False,
                ifb_qdisc_created=False, ifb_ifindex=None,
            )
        if delete_marker:
            self._delete_marker()

    def _install(self, revision: int, config: QoSConfig) -> None:
        marker = self._baseline_marker(config, revision)
        interface_link = self._link(config.interface)
        interface_ifindex = self._link_index(interface_link)
        if interface_ifindex is None:
            raise QosCommandError("interface_not_found")
        marker["interface_ifindex"] = interface_ifindex
        self._save_marker(marker)
        try:
            commands = self._build_install_commands(config, marker)
            for index, command in enumerate(commands):
                self._run(command)
                # These flags are intentionally conservative.  The marker is
                # updated after each owning-object command before later work.
                if command[:4] == ["ip", "link", "add", "name"]:
                    ifb_link = self._link(str(marker["ifb"]))
                    ifb_ifindex = self._link_index(ifb_link)
                    if ifb_ifindex is None or not self._link_is_ifb(ifb_link or {}):
                        raise QosCommandError("ifb_ownership_unverified")
                    self._save_marker_flags(marker, ifb_created=True, ifb_ifindex=ifb_ifindex)
                elif command[:5] == ["ip", "link", "set", "dev", marker["ifb"]] and "alias" in command:
                    ifb_link = self._link(str(marker["ifb"]))
                    ifb_ifindex = self._link_index(ifb_link)
                    if self._link_alias(ifb_link) != marker["ifb_alias"] or ifb_ifindex is None:
                        raise QosCommandError("ifb_ownership_unverified")
                    self._save_marker_flags(marker, ifb_ifindex=ifb_ifindex, ifb_alias_set=True)
                elif command[:3] == ["tc", "qdisc", "add"] and command[command.index("dev") + 1] == marker["ifb"] and "root" in command:
                    self._save_marker_flags(marker, ifb_qdisc_created=True)
                elif command[:3] == ["tc", "qdisc", "add"] and "ingress" in command:
                    self._save_marker_flags(marker, ingress_created=True)
                elif command[:3] == ["tc", "qdisc", "add"] and command[command.index("dev") + 1] == marker["interface"] and "root" in command:
                    self._save_marker_flags(marker, root_created=True)
            if not self._verify_installed(marker):
                raise QosCommandError("tc_verify_failed")
            self._save_applied(revision, config)
            marker["phase"] = "active"
            self._save_marker(marker)
        except Exception:
            try:
                self._remove_owned(marker)
            except Exception:
                # Preserve marker and the original safe error if cleanup could
                # not prove ownership after a partial failure.
                pass
            raise

    def _error_http(self, code: str) -> HTTPException:
        if code in {"interface_required", "interface_not_found"}:
            return HTTPException(422, "QoS 接口配置无效")
        if code.endswith("conflict") or code in {"root_qdisc_ownership_lost", "ingress_qdisc_ownership_lost",
                                                   "ifb_qdisc_ownership_lost", "ifb_ownership_lost",
                                                   "ownership_interface_conflict",
                                                   "ownership_unconfirmed"}:
            return HTTPException(409, "检测到非本服务拥有的 tc/IFB 对象，已拒绝接管")
        if code in {"desired_revision_conflict", "applied_revision_conflict"}:
            return HTTPException(409, "QoS 配置版本已变化，请刷新后重试")
        if code in {"permission_denied", "kernel_feature_missing", "command_unavailable"}:
            return HTTPException(503, "Linux 内核或运行权限不支持 QoS 后端")
        if code in {"object_conflict"}:
            return HTTPException(409, "QoS 目标对象发生变化，请刷新后重试")
        return HTTPException(502, "QoS tc 执行或校验失败")

    def _apply_sync(self, expected_revision: int) -> dict[str, Any]:
        with self._lock:
            try:
                revision, config = self._desired()
                if expected_revision != revision:
                    raise QosCommandError("desired_revision_conflict")
                capability = self.capabilities()
                if not capability["available"]:
                    self._last_error = capability["reason"] or "QoS 后端不可用"
                    raise HTTPException(503, self._last_error)
                old = self._applied()
                old_marker = self._load_marker()
                if old is None and old_marker is not None:
                    raise QosCommandError("ownership_record_without_applied")
                if old is not None and old_marker is None:
                    raise QosCommandError("ownership_record_missing")
                if old is not None and not self._marker_matches_applied(old_marker, old):
                    raise QosCommandError("ownership_record_mismatch")
                if old is not None and old[0] > revision:
                    raise QosCommandError("applied_revision_ahead")
                if old is not None and old[0] == revision and old[1] != config:
                    raise QosCommandError("desired_record_mismatch")
                # Retries are common around an HTTP timeout.  If the exact
                # desired revision/config is already verified in the kernel,
                # return its current public status instead of tearing down and
                # recreating the queues (which would reset counters).
                if (
                    old is not None
                    and old[0] == revision
                    and old[1] == config
                    and old_marker is not None
                    and old_marker.get("phase") == "active"
                    and self._verify_installed(old_marker)
                ):
                    self._last_error = None
                    return self.status()
                old_removed = False
                if old is not None:
                    if not self._verify_installed(old_marker):
                        raise QosCommandError("active_tc_state_invalid")
                    self._preflight(config, ignore_marker=old_marker.get("interface") != config.interface)
                    self._remove_owned(old_marker)
                    self._delete_applied()
                    old_removed = True
                else:
                    self._preflight(config)
                try:
                    self._install(revision, config)
                except Exception as install_error:
                    if old is not None and old_removed:
                        try:
                            self._install(old[0], old[1])
                        except Exception:
                            self._last_error = "apply_failed_restore_failed"
                            raise QosCommandError("apply_failed_restore_failed") from install_error
                    raise
                self._last_error = None
                return self.status()
            except HTTPException:
                raise
            except QosCommandError as exc:
                self._last_error = exc.code
                raise self._error_http(exc.code) from None

    async def apply(self, expected_revision: int) -> dict[str, Any]:
        return await asyncio.to_thread(self._apply_sync, _strict_revision(expected_revision))

    def _put_config_sync(self, expected_revision: int, config: QoSConfig) -> dict[str, Any]:
        with self._lock:
            revision, _ = self._desired()
            if expected_revision != revision:
                raise HTTPException(409, "QoS 配置版本已变化，请刷新后重试")
            self._save_desired(revision + 1, config)
            self._last_error = None
            return self.status()

    def put_config(self, expected_revision: int, config: QoSConfig | Mapping[str, Any]) -> dict[str, Any]:
        parsed = config if isinstance(config, QoSConfig) else QoSConfig.model_validate(config)
        return self._put_config_sync(_strict_revision(expected_revision), parsed)

    def _clear_sync(self, expected_revision: int | None = None) -> dict[str, Any]:
        with self._lock:
            try:
                marker = self._load_marker()
                applied = self._applied()
            except QosCommandError as exc:
                self._last_error = exc.code
                raise self._error_http(exc.code) from None
            # Validate the caller's source generation before checking
            # capabilities or issuing any tc/ip mutation.  A missing pair is
            # already fully cleared and is idempotently successful.
            if expected_revision is not None:
                try:
                    expected_revision = _strict_revision(expected_revision)
                except ValueError:
                    raise HTTPException(422, "QoS 清理版本必须是正整数") from None
                if expected_revision < 1:
                    raise HTTPException(422, "QoS 清理版本必须是正整数")
            cleanup_revision = applied[0] if applied is not None else (
                marker.get("revision") if marker is not None else None
            )
            if expected_revision is not None and cleanup_revision is not None:
                if expected_revision != cleanup_revision:
                    raise HTTPException(409, "QoS 配置版本已变化，请刷新后重试")
            if marker is not None and applied is not None and not self._marker_matches_applied(marker, applied):
                self._last_error = "ownership_record_mismatch"
                raise self._error_http("ownership_record_mismatch")
            if marker is None and applied is not None:
                # The DB record alone cannot prove that it is safe to remove
                # kernel objects.  Never turn this state into a successful
                # "disabled" response by deleting only the record.
                self._last_error = "ownership_record_missing"
                raise self._error_http("ownership_record_missing")
            if marker is None:
                self._last_error = None
                return self.status()
            capability = self.capabilities()
            if not capability["available"]:
                self._last_error = capability["reason"] or "QoS 后端不可用"
                raise HTTPException(503, self._last_error)
            try:
                # Keep the checkpoint marker until the applied record is
                # removed.  If the state store fails between those writes,
                # the remaining cleanup marker is enough to retry safely.
                self._remove_owned(marker, delete_marker=False)
                if applied is not None:
                    self._delete_applied()
                self._delete_marker()
                self._last_error = None
            except QosCommandError as exc:
                self._last_error = exc.code
                raise self._error_http(exc.code) from None
            return self.status()

    async def clear_applied(self, expected_revision: int | None = None) -> dict[str, Any]:
        return await asyncio.to_thread(self._clear_sync, expected_revision)

    def _recover_sync(self) -> None:
        with self._lock:
            try:
                marker = self._load_marker()
                applied = self._applied()
                if applied is not None and marker is None:
                    self._last_error = "ownership_record_missing"
                elif marker is not None and marker.get("phase") != "active":
                    self._last_error = "incomplete_apply_record"
                elif applied is not None and marker is not None and not self._marker_matches_applied(marker, applied):
                    self._last_error = "ownership_record_mismatch"
                elif applied is not None and marker is not None and self.capabilities()["available"]:
                    self._last_error = None if self._verify_installed(marker) else "tc_state_mismatch"
                else:
                    self._last_error = None
            except QosCommandError as exc:
                self._last_error = exc.code
            except Exception:
                # A stale or unreadable QoS state must not prevent unrelated
                # R-Link services from starting.
                self._last_error = "qos_recovery_failed"

    async def recover(self) -> None:
        await asyncio.to_thread(self._recover_sync)

    def _class_statistics(self, device: str, parent: str) -> dict[str, int | None] | None:
        try:
            payload = self._run_json(["tc", "-s", "-j", "class", "show", "dev", device, "parent", parent])
        except QosCommandError:
            return None
        items = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []
        total = {"bytes": 0, "drops": 0, "backlog_bytes": 0}
        seen = False
        for item in items:
            if not isinstance(item, Mapping):
                continue
            sources: list[Mapping[str, Any]] = [item]
            for key in ("stats2", "stats", "basic"):
                value = item.get(key)
                if isinstance(value, Mapping):
                    sources.insert(0, value)

            def first_value(key: str) -> Any:
                for source in sources:
                    if key in source:
                        return source.get(key)
                return None

            for key, target in (("bytes", "bytes"), ("drops", "drops")):
                value = first_value(key)
                if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value >= 0:
                    total[target] += int(value)
                    seen = True
            backlog = first_value("backlog")
            if isinstance(backlog, Mapping):
                value = backlog.get("bytes")
            else:
                value = backlog
            if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value >= 0:
                total["backlog_bytes"] += int(value)
                seen = True
        return total if seen else None

    def _statistics(self, marker: Mapping[str, Any] | None, state: str) -> dict[str, Any]:
        if state != "active" or marker is None:
            return {}
        return {
            "download": self._class_statistics(str(marker["interface"]), str(marker["root_handle"])),
            "upload": self._class_statistics(str(marker["ifb"]), str(marker["ifb_handle"])),
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            capability = self.capabilities()
            desired_error: str | None = None
            applied_error: str | None = None
            marker_error: str | None = None
            try:
                revision, config = self._desired()
            except QosCommandError as exc:
                revision, config = 0, _default_config()
                desired_error = exc.code
            try:
                applied_item = self._applied()
            except QosCommandError as exc:
                applied_item = None
                applied_error = exc.code
            try:
                marker = self._load_marker()
            except QosCommandError as exc:
                marker = None
                marker_error = exc.code
            if desired_error or applied_error or marker_error:
                self._last_error = desired_error or applied_error or marker_error
            applied = None
            if applied_item is not None:
                applied = {"revision": applied_item[0], "config": _json_config(applied_item[1])}
            state = "unavailable" if not capability["available"] else ("inactive" if applied_item is None else "error")
            error = self._last_error
            if desired_error:
                state, error = "error", desired_error
            elif applied_error:
                state, error = "error", applied_error
            elif marker_error:
                state, error = "error", marker_error
            elif applied_item is not None and marker is None:
                state, error = "error", "ownership_record_missing"
            elif marker is not None and applied_item is None:
                state, error = "error", "applied_record_missing"
            elif marker is not None and marker.get("phase") != "active":
                state, error = "error", "incomplete_apply_record"
            elif applied_item is not None and marker is not None and not self._marker_matches_applied(marker, applied_item):
                state, error = "error", "ownership_record_mismatch"
            elif applied_item is not None and applied_item[0] == revision and applied_item[1] != config:
                state, error = "error", "desired_record_mismatch"
            elif applied_item is not None and marker is not None and capability["available"]:
                try:
                    if self._verify_installed(marker):
                        state = "active" if applied_item[0] == revision else "pending"
                        error = None
                    else:
                        state, error = "error", "tc_state_mismatch"
                except QosCommandError as exc:
                    state, error = "error", exc.code
            elif capability["available"] and applied_item is None:
                state = "pending" if revision > 0 else "inactive"
                error = self._last_error
            elif not capability["available"]:
                state = "unavailable"
                error = capability["reason"] or self._last_error
            cleanup_revision = applied_item[0] if applied_item is not None else (
                marker.get("revision") if marker is not None else None
            )
            if applied_item is not None and applied_item[0] > revision:
                state, error = "error", "applied_revision_ahead"
            return {
                "capabilities": capability,
                "desired": {"revision": revision, "config": _json_config(config)},
                "applied": applied,
                "state": state,
                "error": error,
                "cleanup_revision": cleanup_revision,
                "statistics": self._statistics(marker if state == "active" else None, state),
            }


# Public spelling used by the parent service.
QoSManager = QosManager
