"""Application boundary snapshots; wire validation remains owned by R-SDK."""

from __future__ import annotations

import json
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from ._vendor.r_sdk_interop import ContractError, parse, validate

ReadView = Mapping[str, Any]
Json = dict[str, Any]


def seal(request: Json) -> str:
    """Bind every validated field, including actor-independent request metadata."""
    return json.dumps(
        validate(request), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def snapshot(request: Json) -> Json:
    """Give the SDK a private object with no caller-owned nested aliases."""
    return parse(seal(request))


def check_seal(request: Json, expected: str) -> None:
    """Fail closed if an awaited integration rewrites a previously admitted frame."""
    if seal(request) != expected:
        raise ContractError("BINDING_MISMATCH")


def read_view(request: Json) -> ReadView:
    """Native callbacks receive a recursively immutable view of the private frame."""

    def freeze(value: Any) -> Any:
        if isinstance(value, dict):
            return MappingProxyType(
                {key: freeze(child) for key, child in value.items()}
            )
        if isinstance(value, list):
            return tuple(freeze(child) for child in value)
        return value

    return freeze(request)
