"""Keep new background-service state away from the developer's live instance."""
import pytest


@pytest.fixture(autouse=True)
def isolated_services(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DATA_DIR', str(tmp_path / 'services'))
    monkeypatch.setenv('R_LINK_DEVICES_DB', str(tmp_path / 'devices.sqlite'))
    monkeypatch.setenv('R_LINK_DEVICE_SYNC_INTERVAL', '0')
    for name in ('R_LINK_FRPC_BINARY', 'R_LINK_CADDY_BINARY', 'R_LINK_FRP_TOKEN',
                 'R_LINK_CLOUDFLARE_TOKEN', 'R_LINK_DOWNLOAD_ALLOWED_HOSTS', 'R_LINK_DOWNLOAD_MAX_BYTES',
                 'R_LINK_NETBIRD_URL', 'R_LINK_NETBIRD_TOKEN', 'R_LINK_DEVICE_STALE_SECONDS'):
        monkeypatch.delenv(name, raising=False)
