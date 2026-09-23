"""A bounded shared folder, independent of the process working directory."""
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import threading

from fastapi import HTTPException
from core.paths import SERVER_DIR

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 2000
_lock = threading.RLock()
_TEMP_PREFIX = '.rlink-upload-'


@contextmanager
def operation():
    with _lock:
        try:
            yield
        except FileNotFoundError:
            raise HTTPException(404, '文件或目录不存在') from None
        except FileExistsError:
            raise HTTPException(409, '已存在同名文件或目录，不会覆盖') from None
        except PermissionError:
            raise HTTPException(403, '无权访问该文件或文件正在使用') from None
        except OSError:
            raise HTTPException(409, '文件操作失败，请检查目录权限、占用情况及剩余空间') from None


def root():
    path = Path(os.getenv('R_LINK_STORAGE_DIR', str(SERVER_DIR / 'shared'))).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def validate_name(name):
    if (not name or len(name.encode('utf-8')) > 240 or name in {'.', '..'}
            or name.endswith((' ', '.')) or name.startswith(_TEMP_PREFIX)
            or any(ord(c) < 32 or c in '/\\:*?"<>|' for c in name)
            or re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', name, re.I)):
        raise HTTPException(400, '文件名无效')
    return name


def relative_parts(value):
    if not isinstance(value, str) or len(value) > 1800:
        raise HTTPException(400, '路径无效或过长')
    if not value:
        return []
    return [validate_name(part) for part in value.split('/')]


def is_link(info):
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, 'st_file_attributes', 0) & 0x400)


def checked_path(value, *, exists=True):
    base = root()
    current = base
    parts = relative_parts(value)
    for index, part in enumerate(parts):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if not exists and index == len(parts) - 1:
                break
            raise
        if is_link(info) or (stat.S_ISREG(info.st_mode) and info.st_nlink > 1):
            raise HTTPException(403, '共享区不支持符号链接、目录联接或硬链接')
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise HTTPException(403, '不支持此文件类型')
    if not current.resolve().is_relative_to(base):
        raise HTTPException(403, '路径超出共享区')
    return current


def entry(path, relative):
    info = path.stat()
    return {'name': path.name, 'path': relative, 'kind': 'directory' if path.is_dir() else 'file',
            'size': info.st_size if path.is_file() else None,
            'modified_at': datetime.fromtimestamp(info.st_mtime, timezone.utc).isoformat()}


def list_directory(path=''):
    with operation():
        directory = checked_path(path)
        if not directory.is_dir():
            raise HTTPException(400, '目标不是目录')
        entries = []
        skipped = 0
        for index, child in enumerate(directory.iterdir()):
            if index >= MAX_ENTRIES:
                raise HTTPException(409, '目录条目过多，请在服务端拆分为较小目录（最多 2000 项）')
            relative = '/'.join(filter(None, [path, child.name]))
            try:
                checked_path(relative)
                entries.append(entry(child, relative))
            except (HTTPException, FileNotFoundError):
                skipped += 1
        entries.sort(key=lambda item: (item['kind'] != 'directory', item['name'].casefold()))
        return {'path': path, 'entries': entries, 'skipped': skipped, 'max_file_bytes': MAX_FILE_BYTES}


def create_directory(parent, name):
    with operation():
        validate_name(name)
        relative = '/'.join(filter(None, [parent, name]))
        target = checked_path(relative, exists=False)
        target.mkdir()
        return entry(target, relative)


def store_file(parent, name, source):
    with operation():
        validate_name(name)
        relative = '/'.join(filter(None, [parent, name]))
        target = checked_path(relative, exists=False)
        if target.exists():
            raise HTTPException(409, '已存在同名文件或目录，不会覆盖')
        # Publish only a fully written file. Hard-link creation is atomic and
        # fails if another process creates the destination in the meantime.
        fd, temporary = tempfile.mkstemp(prefix=_TEMP_PREFIX, dir=target.parent)
        try:
            with os.fdopen(fd, 'wb') as output:
                shutil.copyfileobj(source, output, 1024 * 1024)
                output.flush()
                os.fsync(output.fileno())
            os.link(temporary, target)
        finally:
            Path(temporary).unlink(missing_ok=True)
        return entry(target, relative)


def open_download(path):
    with operation():
        target = checked_path(path)
        if not target.is_file():
            raise HTTPException(400, '请选择文件下载')
        file = target.open('rb')
        info = os.fstat(file.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or info.st_size > MAX_FILE_BYTES:
            file.close()
            raise HTTPException(413, '文件不可下载或超过 64 MiB 限制')
        return file, target.name, info.st_size


def rename(path, name):
    with operation():
        if not path:
            raise HTTPException(400, '不能重命名共享区根目录')
        validate_name(name)
        source = checked_path(path)
        relative = '/'.join([*relative_parts(path)[:-1], name])
        if relative == path:
            return entry(source, path)
        target = checked_path(relative, exists=False)
        if target.exists():
            raise HTTPException(409, '已存在同名文件或目录，不会覆盖')
        source.rename(target)
        return entry(target, relative)


def remove(path):
    with operation():
        if not path:
            raise HTTPException(400, '不能删除共享区根目录')
        target = checked_path(path)
        if target.is_dir():
            if next(target.iterdir(), None) is not None:
                raise HTTPException(409, '目录非空，请先移走或删除其中的文件')
            target.rmdir()
        else:
            target.unlink()
