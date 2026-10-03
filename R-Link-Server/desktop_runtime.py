"""Frozen desktop server: owned by one desktop process, with graceful shutdown."""
import hmac
import os
from pathlib import Path
import sys
import threading
import time

import psutil
import uvicorn
from fastapi import HTTPException, Request

SERVICE = "r-link"
PORT = int(os.environ.get("RBOX_DESKTOP_PORT", "8210"))
USER_ENV = "R_LINK_USER_ROOT"


def default_user_root():
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local")) / "R-Link"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "r-link"


def configure_runtime(app, server, session):
    @app.get("/rbox/health", include_in_schema=False)
    async def desktop_health():
        return {"status": "healthy", "service": SERVICE, "session": session}

    @app.post("/rbox/shutdown", include_in_schema=False)
    async def desktop_shutdown(request: Request):
        if not session or not hmac.compare_digest(request.headers.get("x-rbox-session", ""), session):
            raise HTTPException(403, "Desktop session required")
        server.should_exit = True
        return {"status": "stopping"}


def watch_parent(server, parent_pid, created):
    while not server.should_exit:
        time.sleep(0.5)
        try:
            parent = psutil.Process(parent_pid)
            if abs(parent.create_time() - created) < 0.01 and parent.is_running():
                continue
        except psutil.Error:
            pass
        server.should_exit = True
        # Bound shutdown even if an application service is stuck during cleanup.
        time.sleep(8)
        os._exit(0)


def main():
    root = Path(os.environ.setdefault(USER_ENV, str(default_user_root())))
    root.mkdir(parents=True, exist_ok=True)
    os.environ["R_LINK_DATA_DIR"] = str(root / "data")
    os.environ["R_LINK_STORAGE_DIR"] = str(root / "shared")
    os.environ["R_LINK_HOST"] = "127.0.0.1"
    os.environ["DEV"] = "false"
    from main import app
    config = uvicorn.Config(app, host="127.0.0.1", port=PORT, reload=False,
                            loop="asyncio", http="h11", ws="websockets", log_level="info")
    server = uvicorn.Server(config)
    session = os.environ.get("RBOX_DESKTOP_SESSION", "")
    configure_runtime(app, server, session)
    parent_pid = int(os.environ.get("RBOX_DESKTOP_PARENT", "0"))
    if parent_pid:
        try:
            created = psutil.Process(parent_pid).create_time()
        except psutil.Error:
            raise SystemExit("Desktop parent is no longer running")
        threading.Thread(target=watch_parent, args=(server, parent_pid, created), daemon=True).start()
    server.run()


if __name__ == "__main__":
    main()
