"""Persistent device inventory. Connectivity is a timestamped TCP observation, not device health."""
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import ipaddress
import os
import re
import sqlite3
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from core.paths import CONFIG_DIR


class DeviceInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=22, ge=1, le=65535, strict=True)
    username: str = Field(default="", max_length=80)

    @field_validator("host")
    @classmethod
    def normalize_host(cls, value):
        try:
            address = ipaddress.ip_address(value)
        except ValueError:
            host = value.rstrip(".").lower()
            if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) or any(
                not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in host.split(".")
            ):
                raise ValueError("Use an IP address or hostname, without a URL or port")
            return host
        if address.is_unspecified or address.is_multicast or str(address) == "255.255.255.255" or "%" in value:
            raise ValueError("Use a unicast device address")
        return str(address)


@contextmanager
def database():
    path = Path(os.getenv("R_LINK_DEVICES_DB", str(CONFIG_DIR / "devices.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    try:
        db.execute("""CREATE TABLE IF NOT EXISTS devices (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, host TEXT NOT NULL, port INTEGER NOT NULL,
            username TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'unchecked', checked_at TEXT, latency_ms REAL,
            UNIQUE(host, port))""")
        with db:
            yield db
    finally:
        db.close()


def get_device(db, device_id):
    row = db.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Device not found")
    return dict(row)


def list_devices():
    with database() as db:
        return [dict(row) for row in db.execute("SELECT * FROM devices ORDER BY name, id")]


def save_device(data: DeviceInput, device_id=None):
    try:
        with database() as db:
            db.execute("BEGIN IMMEDIATE")
            values = (data.name, data.host, data.port, data.username)
            if device_id:
                get_device(db, device_id)
                db.execute("""UPDATE devices SET name=?,host=?,port=?,username=?,revision=revision+1,
                    status='unchecked',checked_at=NULL,latency_ms=NULL WHERE id=?""", (*values, device_id))
            else:
                if db.execute("SELECT COUNT(*) FROM devices").fetchone()[0] >= 256:
                    raise HTTPException(409, "Device limit reached (256)")
                device_id = str(uuid.uuid4())
                db.execute("INSERT INTO devices (name,host,port,username,id) VALUES (?,?,?,?,?)", (*values, device_id))
            return get_device(db, device_id)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "A device with this host and port already exists") from None


def delete_device(device_id):
    with database() as db:
        if not db.execute("DELETE FROM devices WHERE id=?", (device_id,)).rowcount:
            raise HTTPException(404, "Device not found")


def record_probe(device, reachable, latency_ms):
    with database() as db:
        # Editing/deleting a target during a slow probe must never restore stale results.
        db.execute("""UPDATE devices SET status=?,checked_at=?,latency_ms=?
            WHERE id=? AND revision=?""", (
            "reachable" if reachable else "unreachable", datetime.now(timezone.utc).isoformat(),
            latency_ms if reachable else None, device["id"], device["revision"]))
        return get_device(db, device["id"])
