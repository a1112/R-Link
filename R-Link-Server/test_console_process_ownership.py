import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def console():
    spec = importlib.util.spec_from_file_location("console_ownership_tests", Path(__file__).parent / "builtin/ttyd-console/__init__.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_busy_port_and_stale_pid_do_not_mean_our_console_is_running(console, tmp_path, monkeypatch):
    manager = console.TTYDManager(tmp_path)
    manager.pid_file.write_text("12345")
    monkeypatch.setattr(manager, "_is_port_available", lambda _: False)
    assert not manager.is_running()
    kill = Mock()
    monkeypatch.setattr(console.os, "kill", kill)
    monkeypatch.setattr(console.subprocess, "run", kill)
    assert manager.stop()["success"]
    kill.assert_not_called()


def test_only_owned_child_is_stopped(console, tmp_path):
    manager = console.TTYDManager(tmp_path)
    process = Mock(pid=12345)
    process.poll.return_value = None
    manager.process = process
    manager.pid_file.write_text("98765")
    assert manager.is_running()
    assert manager.stop()["success"]
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)
    assert manager.process is None


def test_live_console_configuration_keeps_process_handle(console, tmp_path):
    plugin = console.Plugin(plugin_dir=tmp_path)
    process = Mock()
    process.poll.return_value = None
    plugin.ttyd.process = process
    with pytest.raises(ValueError, match="Stop the console"):
        plugin.set_config({"ttyd_port": 8888})
    assert plugin.ttyd.process is process
    assert plugin.ttyd.ttyd_port == 7681


def test_rejected_plugin_configuration_is_not_saved(tmp_path):
    from core.python_plugin import PythonPlugin, PythonPluginInfo
    plugin_dir = tmp_path / "sample"
    plugin_dir.mkdir()
    (plugin_dir / "manifest.yaml").write_text("name: sample\nentry: __init__.py\n")
    (plugin_dir / "__init__.py").write_text("# fixture")
    info = PythonPluginInfo("sample", "1", "fixture", "test", "__init__.py")
    plugin = PythonPlugin(info, str(plugin_dir))
    plugin.instance = Mock()
    plugin.instance.set_config.return_value = False
    plugin._save_config = Mock()
    assert not plugin.set_config({"port": 9999})
    plugin._save_config.assert_not_called()


@pytest.mark.asyncio
async def test_console_status_uses_child_status_not_python_wrapper(monkeypatch):
    from api import console as api
    plugin = Mock()
    plugin.get_status.return_value = {"status": "running"}
    plugin.instance.get_status.return_value = {"ttyd_running": True, "pid": 123, "console_url": "http://127.0.0.1:7681"}
    monkeypatch.setattr(api, "get_console_plugin", lambda: plugin)
    assert (await api.get_console_status())["pid"] == 123
    plugin.get_status.assert_not_called()
    plugin.instance = None
    assert (await api.get_console_status())["ttyd_running"] is False


def test_failed_plugin_stop_does_not_drop_handle_or_restart(tmp_path):
    from core.python_plugin import PythonPlugin, PythonPluginInfo, PythonPluginStatus
    plugin = PythonPlugin(PythonPluginInfo("sample", "1", "fixture", "test", "__init__.py"), str(tmp_path))
    plugin.instance = Mock()
    plugin.instance.stop.return_value = False
    plugin.status = PythonPluginStatus.RUNNING
    plugin.start = Mock()
    assert not plugin.restart()
    assert plugin.status == PythonPluginStatus.RUNNING
    plugin.start.assert_not_called()
