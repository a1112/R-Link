"""Resolve server data independently of the caller's working directory."""
import os
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
USER_ROOT = Path(os.getenv("R_LINK_USER_ROOT", str(SERVER_DIR))).resolve()
USER_ROOT.mkdir(parents=True, exist_ok=True)
PLUGINS_DIR = USER_ROOT / "plugins"
BUILTIN_DIR = SERVER_DIR / "builtin"
CONFIG_DIR = USER_ROOT / "config"
LOGS_DIR = USER_ROOT / "logs"
