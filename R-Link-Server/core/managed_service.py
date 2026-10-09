"""Only control processes started by this service; never terminate by port/name."""
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import subprocess
import threading

import psutil
from fastapi import HTTPException
from core.paths import SERVER_DIR


def executable(env, name):
    configured = os.getenv(env)
    bundled = SERVER_DIR.parent / 'binaries' / (name + ('.exe' if os.name == 'nt' else ''))
    found = str(Path(configured).resolve()) if configured else (shutil.which(name) or (str(bundled) if bundled.is_file() else None))
    if not found or not Path(found).is_file():
        raise HTTPException(503, f'未安装 {name}；请设置 {env} 为程序绝对路径')
    if configured and not Path(configured).is_absolute():
        raise HTTPException(503, f'{env} 必须为绝对路径')
    return found


def private_json(path, value):
    import json
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as file:
        json.dump(value, file, ensure_ascii=False)
    temporary.replace(path)


def child_environment(*, direct_network=False):
    # Service credentials are not needed by the external executables. FRP reads
    # HTTP_PROXY implicitly, which can send even loopback servers to a proxy.
    proxies = {'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY'} if direct_network else set()
    return {key: value for key, value in os.environ.items()
            if not key.upper().startswith('R_LINK_') and key.upper() not in proxies}


class ManagedService:
    def __init__(self, state, key):
        self.state, self.key = state, key
        self.directory = state.root / 'processes' / key
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.process = None
        self.reader = None
        self.error = None

    def status(self):
        if self.process is None:
            return {'state': 'error' if self.error else 'stopped', 'pid': None, 'error': self.error}
        code = self.process.poll()
        return {'state': 'running' if code is None else 'error', 'pid': self.process.pid if code is None else None,
                'error': None if code is None else f'进程已退出，退出码 {code}；请查看日志'}

    async def start(self, args, *, env=None, secrets=()):
        if self.status()['state'] == 'running':
            return self.status()
        await self.stop()
        self.error = None
        handler = RotatingFileHandler(self.directory / 'output.log', maxBytes=1024 * 1024, backupCount=2, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(message)s'))
        try:
            self.process = subprocess.Popen(args, cwd=self.directory, env=child_environment() if env is None else env, stdin=subprocess.DEVNULL,
                                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except OSError as exc:
            handler.close()
            code = getattr(exc, 'winerror', None) or exc.errno
            self.error = f'程序启动失败（系统错误 {code}），请检查执行权限和依赖'
            raise HTTPException(503, self.error) from None
        process = self.process
        try:
            image = str(Path(args[0]).resolve())
            try:
                native = psutil.Process(process.pid)
                created = native.create_time()
                # Launchers can exec a different image (e.g. macOS Python.app).
                image = native.exe()
            except psutil.NoSuchProcess:
                created = 0
            self.state.save('process', {'pid': process.pid, 'created': created, 'executable': image,
                                        'cwd': str(self.directory)}, self.key)
        except Exception:
            # If persistence fails, do not leave an untracked child behind.
            if process.poll() is None:
                process.kill()
            await asyncio.to_thread(process.wait, timeout=5)
            process.stdout.close()
            handler.close()
            self.process = None
            raise

        def consume():
            try:
                while True:
                    line = process.stdout.readline(8192)
                    if not line:
                        break
                    text = line.decode('utf-8', errors='replace').rstrip()
                    for secret in secrets:
                        if secret:
                            text = text.replace(secret, '[redacted]')
                    handler.emit(logging.LogRecord(self.key, logging.INFO, '', 0, text, (), None))
            finally:
                process.stdout.close()
                handler.close()
        self.reader = threading.Thread(target=consume, daemon=True)
        self.reader.start()
        await asyncio.sleep(0.2)
        if self.process.poll() is not None:
            raise HTTPException(502, self.status()['error'])
        try:
            native = psutil.Process(process.pid)
            if abs(native.create_time() - created) >= 0.01:
                raise RuntimeError('Owned service process identity changed during startup')
            # A launcher may still have been running during the first snapshot.
            self.state.save('process', {'pid': process.pid, 'created': created, 'executable': native.exe(),
                                        'cwd': str(self.directory)}, self.key)
        except Exception:
            await self.stop()
            raise
        return self.status()

    async def stop(self):
        owned = self.process
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    await asyncio.to_thread(self.process.wait, timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    await asyncio.to_thread(self.process.wait, timeout=5)
            if self.reader:
                await asyncio.to_thread(self.reader.join, 2)
            self.process = None
        if owned and any(item['id'] == self.key and item['pid'] == owned.pid for item in self.state.list('process')):
            self.state.delete('process', self.key)
        self.error = None

    def logs(self):
        path = self.directory / 'output.log'
        if not path.exists():
            return ''
        with path.open('rb') as file:
            file.seek(max(0, path.stat().st_size - 32768))
            return file.read(32768).decode('utf-8', errors='replace')


async def recover_processes(state):
    """Recover after an unclean server exit, checking identity against PID reuse."""
    for item in state.list('process'):
        try:
            process = psutil.Process(item['pid'])
            if (abs(process.create_time() - item['created']) < 0.01
                    and Path(process.exe()).resolve() == Path(item['executable']).resolve()
                    and Path(process.cwd()).resolve() == Path(item['cwd']).resolve()):
                process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=5)
                except psutil.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, timeout=5)
        except psutil.NoSuchProcess:
            pass
        except psutil.AccessDenied as exc:
            raise RuntimeError('Cannot safely recover an owned service process') from exc
        state.delete('process', item['id'])
