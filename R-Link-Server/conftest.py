"""Keep new background-service state away from the developer's live instance."""
import pytest


@pytest.fixture(autouse=True)
def isolated_services(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_DATA_DIR', str(tmp_path / 'services'))
    for name in ('R_LINK_FRPC_BINARY', 'R_LINK_CADDY_BINARY', 'R_LINK_FRP_TOKEN',
                 'R_LINK_CLOUDFLARE_TOKEN', 'R_LINK_DOWNLOAD_ALLOWED_HOSTS', 'R_LINK_DOWNLOAD_MAX_BYTES'):
        monkeypatch.delenv(name, raising=False)
