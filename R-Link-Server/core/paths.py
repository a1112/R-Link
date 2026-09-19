"""Resolve server data independently of the caller's working directory."""
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parents[1]
PLUGINS_DIR = SERVER_DIR / "plugins"
BUILTIN_DIR = SERVER_DIR / "builtin"
CONFIG_DIR = SERVER_DIR / "config"
LOGS_DIR = SERVER_DIR / "logs"
