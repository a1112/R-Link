"""Application-owned read adapters consuming a pinned R-SDK source snapshot."""

from ._vendor.r_sdk_interop import Client, ContractError, parse, validate
from .service import ReadService, Settings

__all__ = ["Client", "ContractError", "ReadService", "Settings", "parse", "validate"]
