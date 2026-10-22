"""Protocol boundaries found during independent Clash integration review."""
import gzip
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from core.clash import (ClashManager, ClashSettingsInput, ProxySelection, _normalize_managed_config,
                        _profile_config, _sensitive_values)
from core.service_state import ServiceState


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [{}, [], {'version': None}, {'version': ''}, {'version': 42}])
async def test_unrelated_json_cannot_report_a_connected_clash(tmp_path, payload):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save('settings', {'controller_url': 'http://127.0.0.1:9090'}, 'clash')
    manager._json_request = AsyncMock(return_value=payload)
    status = await manager.status()
    assert status['configured'] and not status['connected'] and status['error']


@pytest.mark.asyncio
async def test_names_keep_literal_percent_and_selection_spaces(tmp_path):
    manager = ClashManager(ServiceState(tmp_path))
    manager._response = AsyncMock()
    await manager.select_proxy('香港%20 / 组', ProxySelection(name=' node with spaces '))
    assert '%2520' in manager._response.call_args.args[1]
    assert manager._response.call_args.kwargs['json_body'] == {'name': ' node with spaces '}


@pytest.mark.asyncio
async def test_controller_decompresses_once_and_rejects_redirects(tmp_path, monkeypatch):
    manager = ClashManager(ServiceState(tmp_path))
    manager.state.save('settings', {'controller_url': 'http://127.0.0.1:9090', 'secret': 'private'}, 'clash')
    real_client = httpx.AsyncClient
    redirect = False

    def handle(request):
        assert request.headers['Authorization'] == 'Bearer private'
        if redirect:
            return httpx.Response(302, headers={'Location': 'https://other.invalid'})
        return httpx.Response(200, content=gzip.compress(json.dumps({'version': 'v-test'}).encode()),
                              headers={'Content-Encoding': 'gzip'})

    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handle), **kwargs))
    assert (await manager.status())['version'] == 'v-test'
    redirect = True
    status = await manager.status()
    assert not status['connected'] and '重定向' in status['error']


def test_yaml_alias_graph_is_bounded_and_deep_input_is_rejected():
    content = 'a0: &a0 [secret]\n'
    for index in range(1, 18):
        content += f'a{index}: &a{index} [' + ', '.join([f'*a{index - 1}'] * 8) + ']\n'
    config = _profile_config(content)
    assert _sensitive_values(config) == ()
    with pytest.raises(HTTPException) as error:
        _profile_config('value: ' + '[' * 1500 + 'x' + ']' * 1500)
    assert error.value.status_code == 422


def test_legacy_inlets_removed_and_provider_cache_names_do_not_collide(tmp_path):
    forbidden = {'external-controller-pipe': 'pipe-name', 'ss-config': 'ss://unsafe',
                 'vmess-config': 'vmess://unsafe', 'tuic-server': {'enable': True},
                 'external-ui-url': 'https://unrelated.invalid/dashboard.zip'}
    normalized = _normalize_managed_config(dict(forbidden, **{
        'ntp': {'enable': True, 'write-to-system': True},
        'proxy-providers': {'香港': {'url': 'https://one.invalid'}, '台湾': {'url': 'https://two.invalid'}},
        'rule-providers': {'香港': {'url': 'https://rules.invalid'}},
    }), 'http://127.0.0.1:9000', 'secret', tmp_path, 9001)
    assert all(key not in normalized for key in forbidden)
    assert not normalized['ntp']['write-to-system']
    paths = [provider['path'] for section in ('proxy-providers', 'rule-providers')
             for provider in normalized[section].values()]
    assert len(set(paths)) == 3


def test_secret_is_valid_for_http_headers():
    with pytest.raises(ValueError):
        ClashSettingsInput(controller_url='http://127.0.0.1:9090', secret='非ASCII密钥')
