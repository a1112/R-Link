"""Keep new background-service state away from the developer's live instance."""
import pytest


@pytest.fixture(autouse=True)
def isolated_services(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DATA_DIR', str(tmp_path / 'services'))
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.sqlite'))
    monkeypatch.setenv('R_LINK_AUTH_DB', str(tmp_path / 'auth.sqlite'))
    monkeypatch.setenv('R_LINK_DEVICE_SYNC_INTERVAL', '0')
    monkeypatch.setenv('R_LINK_RFILE_INTERVAL', '0')
    for name in ('R_LINK_FRPC_BINARY', 'R_LINK_CADDY_BINARY', 'R_LINK_FRP_TOKEN',
                 'R_LINK_CLOUDFLARE_TOKEN', 'R_LINK_DOWNLOAD_ALLOWED_HOSTS', 'R_LINK_DOWNLOAD_MAX_BYTES',
                 'R_LINK_NETBIRD_URL', 'R_LINK_NETBIRD_TOKEN', 'R_LINK_DEVICE_STALE_SECONDS',
                 'R_LINK_RFILE_URL', 'R_LINK_RFILE_BRIDGE_URL', 'R_LINK_RFILE_TOKEN',
                 'R_LINK_RFILE_SESSION_TOKEN', 'R_LINK_RFILE_ROOT', 'R_LINK_RFILE_CA_CERT',
                 'RFILE_SERVICE_URL', 'RFILE_BRIDGE_URL', 'RFILE_SERVICE_ACCESS_TOKEN', 'RFILE_ALLOWED_ROOTS'):
        monkeypatch.delenv(name, raising=False)
