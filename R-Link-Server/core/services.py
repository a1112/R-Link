"""Application-scoped service owners; all workers stop before releasing the lock."""
from core.service_state import ServiceState
from core.managed_service import executable, recover_processes
from core.downloads import DownloadManager
from core.tunnels import TunnelManager
from core.domains import DomainManager
from fastapi import HTTPException


class Services:
    def __init__(self):
        self.state = ServiceState()
        self.downloads = DownloadManager(self.state)
        self.tunnels = TunnelManager(self.state)
        self.domains = DomainManager(self.state)
        self.ready = False
        self.owns_lock = False

    async def start(self):
        self.state.acquire()
        self.owns_lock = True
        try:
            await recover_processes(self.state)
            await self.tunnels.recover()
            await self.domains.recover()
            await self.downloads.recover()
            self.ready = True
        except BaseException:
            await self.close()
            raise

    async def close(self):
        self.ready = False
        if not self.owns_lock:
            return
        try:
            await self.downloads.close()
        finally:
            try:
                await self.tunnels.close()
            finally:
                try:
                    await self.domains.process.stop()
                finally:
                    self.owns_lock = False
                    self.state.release()

    def capabilities(self):
        result = {'ready': self.ready, 'mode': 'single-operator', 'downloads': {'available': True, 'max_bytes': self.downloads.max_bytes}}
        for name, env, binary in [('frp', 'R_LINK_FRPC_BINARY', 'frpc'), ('https', 'R_LINK_CADDY_BINARY', 'caddy')]:
            try:
                executable(env, binary)
                result[name] = {'available': True, 'reason': None}
            except HTTPException as exc:
                result[name] = {'available': False, 'reason': exc.detail}
        return result
