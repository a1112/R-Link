"""Validate plugin package paths before writing or removing files."""
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

import yaml
from fastapi import HTTPException

MAX_PACKAGE_BYTES = 100 * 1024 * 1024


def plugin_path(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", name):
        raise HTTPException(400, "Invalid plugin name")
    if name.lower() in {"temp", "con", "prn", "aux", "nul", *(f"com{i}" for i in range(10)), *(f"lpt{i}" for i in range(10))}:
        raise HTTPException(400, "Reserved plugin name")
    root = root.resolve()
    target = root / name
    if target.is_symlink() or target.resolve().parent != root:
        raise HTTPException(400, "Unsafe plugin path")
    return target


def safe_extract_zip(archive: zipfile.ZipFile, destination: Path) -> None:
    members = archive.infolist()
    if len(members) > 10000 or sum(member.file_size for member in members) > MAX_PACKAGE_BYTES:
        raise HTTPException(413, "Plugin archive is too large")
    destination = destination.resolve()
    for member in members:
        posix, windows = PurePosixPath(member.filename), PureWindowsPath(member.filename)
        if (posix.is_absolute() or windows.drive or windows.root
                or ".." in posix.parts or ".." in windows.parts
                or "\\" in member.filename or ":" in member.filename
                or stat.S_ISLNK(member.external_attr >> 16)):
            raise HTTPException(400, "ZIP archive contains unsafe paths")
        target = (destination / member.filename).resolve()
        if target != destination and destination not in target.parents:
            raise HTTPException(400, "ZIP archive contains unsafe paths")
    archive.extractall(destination)


def install_zip(zip_path: Path, root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    # Extraction never lives under the plugin discovery directory.
    with tempfile.TemporaryDirectory(prefix="rlink-package-") as temporary:
        staging = Path(temporary)
        try:
            with zipfile.ZipFile(zip_path) as archive:
                safe_extract_zip(archive, staging)
        except zipfile.BadZipFile as error:
            raise HTTPException(400, "Invalid ZIP archive") from error
        manifests = sorted([*staging.rglob("manifest.yaml"), *staging.rglob("manifest.json")])
        if len(manifests) != 1:
            raise HTTPException(400, "Package must contain exactly one plugin manifest")
        manifest = manifests[0]
        try:
            data = yaml.safe_load(manifest.read_text(encoding="utf-8")) if manifest.suffix == ".yaml" else json.loads(manifest.read_text(encoding="utf-8"))
        except (ValueError, yaml.YAMLError, UnicodeError) as error:
            raise HTTPException(400, "Invalid plugin manifest") from error
        if not isinstance(data, dict):
            raise HTTPException(400, "Invalid plugin manifest")
        name = data.get("name")
        target = plugin_path(root, name)
        if target.exists():
            raise HTTPException(409, "Plugin already installed; uninstall it before replacing")
        entry = data.get("binary") or data.get("entry") or data.get("entry_file") or "__init__.py"
        if not isinstance(entry, str):
            raise HTTPException(400, "Invalid plugin entry")
        source = manifest.parent.resolve()
        entry_path = (source / entry).resolve()
        if PureWindowsPath(entry).drive or source not in entry_path.parents or not entry_path.is_file():
            raise HTTPException(400, "Plugin entry must be a file inside the package")
        shutil.move(str(source), str(target))
    return name
