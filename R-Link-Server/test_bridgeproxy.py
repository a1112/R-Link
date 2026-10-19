"""Core facade contracts over isolated transports; no real Core or network changes."""
import asyncio
import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.bridgeproxy import router
from core import bridgeproxy, identity
from core.bridgeproxy import BridgeProxy, CONTRACT, READ_PATHS, WRITE_ROUTES, allowed_route

READ_TOKEN = 'a' * 64
CONTROL_TOKEN = 'b' * 64
REVISION = 'c' * 64
OPERATION = 'd' * 64


def configured(monkeypatch, handler, *, control=True, endpoint='http://127.0.0.1:17893'):
    monkeypatch.setenv('R_LINK_BRIDGEPROXY_URL', endpoint)
    monkeypatch.setenv('R_LINK_BRIDGEPROXY_READ_TOKEN', READ_TOKEN)
    if control:
        monkeypatch.setenv('R_LINK_BRIDGEPROXY_CONTROL_TOKEN', CONTROL_TOKEN)
    return BridgeProxy(transport=httpx.MockTransport(handler))


def core_reply(data, status=200, **kwargs):
    return httpx.Response(status, json={'api_version': 'v1', 'data': data}, **kwargs)


def application(service):
    app = FastAPI()
    app.state.bridgeproxy = service
    app.include_router(router)
    return app


def oidc_session(monkeypatch, role='viewer'):
    monkeypatch.setenv('R_LINK_AUTH_MODE', 'oidc')
    monkeypatch.setenv('R_LINK_OIDC_ISSUER', 'https://id.example/realms/rlink')
    monkeypatch.setenv('R_LINK_OIDC_CLIENT_ID', 'rlink')
    monkeypatch.setenv('R_LINK_OIDC_CLIENT_SECRET', 'isolated-test-client-secret')
    monkeypatch.setenv('R_LINK_PUBLIC_URL', 'https://app.example')
    user = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': role, 'name': role})
    with identity.database() as db:
        db.execute('UPDATE users SET role=? WHERE id=?', (role, user['id']))
        user = dict(db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone())
    session = identity.create_session(user, 'desktop')
    return session, {'Authorization': 'Bearer ' + session['token'],
                     'X-R-Link-Session-Context': session['id']}


@pytest.mark.asyncio
async def test_disabled_adapter_never_contacts_core_or_reports_online(monkeypatch):
    def unexpected(_):
        pytest.fail('Unconfigured adapter contacted a Core')
    service = BridgeProxy(transport=httpx.MockTransport(unexpected))
    try:
        metadata = service.adapter().body['data']
        assert metadata['configured'] is False and metadata['state'] == 'unavailable'
        assert metadata['target'] == 'server' and metadata['endpoint_scope'] == 'server-loopback'
        result = await service.request('GET', '/status')
        assert result.status == 503 and result.body['error']['code'] == 'bridgeproxy_unconfigured'
        assert 'running' not in json.dumps(metadata)
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('endpoint', ['https://127.0.0.1:17893', 'http://127.0.0.2:17893',
                                    'http://192.168.1.2:17893', 'http://example.com:17893',
                                    'http://user:pass@127.0.0.1:17893', 'http://127.0.0.1:17893/v1',
                                    'http://127.0.0.1:17893?url=x', 'http://127.0.0.1:0',
                                    'http://127.0.0.1:65536', 'http://127.0.0.1'])
async def test_only_explicit_server_loopback_endpoint_is_admitted(monkeypatch, endpoint):
    service = configured(monkeypatch, lambda _: pytest.fail('Invalid endpoint contacted'), endpoint=endpoint)
    try:
        assert service.adapter().body['data']['configured'] is False
        assert (await service.request('GET', '/status')).status == 503
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_read_transport_keeps_host_credentials_scopes_and_revision(monkeypatch):
    requests = []
    def upstream(request):
        requests.append(request)
        return core_reply({'revision': REVISION, 'config': {'name': 'Core', 'password': 'hidden'}},
                          headers={'ETag': '"' + REVISION + '"'})
    monkeypatch.setenv('HTTP_PROXY', 'http://environment-proxy.invalid:9999')
    service = configured(monkeypatch, upstream, endpoint='http://localhost:17893/')
    try:
        result = await service.request('GET', '/config')
        assert result.status == 200 and result.headers['ETag'] == '"' + REVISION + '"'
        assert result.body['data']['revision'] == REVISION
        assert 'password' not in result.body['data']['config']
        assert str(requests[0].url) == 'http://127.0.0.1:17893/v1/config'
        assert requests[0].headers['Authorization'] == 'Bearer ' + READ_TOKEN
        assert requests[0].headers['Connection'] == 'close'
        assert not set(requests[0].headers) & {'origin', 'cookie', 'sec-fetch-site', 'x-r-link-csrf'}
        assert not service._client._trust_env and not service._client.follow_redirects
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_write_preserves_bytes_revision_idempotency_and_202_then_operation_error(monkeypatch):
    requests = []
    raw = b'{ "outbound": {"custom_json": "private-custom", "password": "private-password"}, "apply":false }'
    def upstream(request):
        requests.append(request)
        if request.method == 'GET':
            return core_reply({'operation_id': OPERATION, 'status': 'failed', 'error': {
                'status': 412, 'code': 'revision_mismatch', 'message': 'configuration changed'}})
        return core_reply({'operation_id': OPERATION, 'status': 'queued'}, status=202)
    service = configured(monkeypatch, upstream)
    try:
        accepted = await service.request('PATCH', '/config', body=raw, if_match='"' + REVISION + '"',
                                         idempotency_key='one-original-key')
        assert accepted.status == 202 and accepted.body['data']['status'] == 'queued'
        assert requests[0].content == raw
        assert requests[0].headers['If-Match'] == '"' + REVISION + '"'
        assert requests[0].headers['Idempotency-Key'] == 'one-original-key'
        assert requests[0].headers['Authorization'] == 'Bearer ' + CONTROL_TOKEN
        operation = await service.request('GET', '/operations/' + OPERATION)
        assert operation.status == 200 and operation.body['data']['error']['status'] == 412
        assert len(requests) == 2
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [400, 401, 403, 404, 409, 412, 428, 429, 503])
async def test_upstream_error_status_and_business_code_are_preserved(monkeypatch, status):
    service = configured(monkeypatch, lambda _: httpx.Response(status, json={
        'api_version': 'v1', 'error': {'status': status, 'code': 'upstream_code',
                                     'message': 'safe message ' + READ_TOKEN}}))
    try:
        result = await service.request('GET', '/status')
        assert result.status == status and result.body['error']['code'] == 'upstream_code'
        assert READ_TOKEN not in json.dumps(result.body)
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_pairing_codes_only_cross_the_explicit_control_view(monkeypatch):
    requests = []
    def upstream(request):
        requests.append(request)
        return core_reply({'pending': [{'verification_code': '12345678'}], 'result': {
            'verification_code': '87654321', 'token': READ_TOKEN, 'custom_json': 'hidden'}})
    service = configured(monkeypatch, upstream)
    try:
        for path in ('/pairings', '/snapshot', '/operations'):
            result = await service.request('GET', path)
            assert 'verification_code' not in json.dumps(result.body)
            assert 'token' not in result.body['data']['result']
        result = await service.request('GET', '/pairings', control=True, allow_sas=True)
        assert result.body['data']['pending'][0]['verification_code'] == '12345678'
        assert requests[-1].headers['Authorization'] == 'Bearer ' + CONTROL_TOKEN
        assert all(request.headers['Authorization'] == 'Bearer ' + READ_TOKEN for request in requests[:-1])
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_openapi_keeps_write_only_field_definitions_but_removes_secret_examples(monkeypatch):
    spec = {'openapi': '3.1.0', 'components': {'schemas': {'Outbound': {
        'properties': {'password': {'type': 'string', 'writeOnly': True},
                       'custom_json': {'type': 'string', 'writeOnly': True}},
        'example': {'password': 'private-example', 'custom_json': 'private-custom'}}}}}
    service = configured(monkeypatch, lambda _: core_reply(spec))
    try:
        result = (await service.request('GET', '/openapi.json')).body['data']
        fields = result['components']['schemas']['Outbound']
        assert fields['properties']['password']['writeOnly']
        assert fields['properties']['custom_json']['writeOnly']
        assert not fields['example']
    finally:
        await service.close()


class Chunks(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b'x' * 20
        yield b'x' * 20


@pytest.mark.asyncio
async def test_response_boundary_rejects_streaming_oversize_malformed_json_and_redirects(monkeypatch):
    replies = [httpx.Response(200, headers={'Content-Type': 'application/json'}, stream=Chunks()),
               httpx.Response(200, content=b'{"api_version":"v1","data":{},"data":{}}',
                              headers={'Content-Type': 'application/json'}),
               httpx.Response(307, headers={'Location': 'https://other.invalid/private'}),
               httpx.Response(200, json={'api_version': 'v1', 'data': {}},
                              headers={'Content-Length': '99999999'})]
    requests = []
    def upstream(request):
        requests.append(request)
        return replies.pop(0)
    service = configured(monkeypatch, upstream)
    try:
        monkeypatch.setattr(bridgeproxy, 'MAX_RESPONSE_BYTES', 32)
        assert (await service.request('GET', '/status')).body['error']['code'] == 'bridgeproxy_response_too_large'
        monkeypatch.setattr(bridgeproxy, 'MAX_RESPONSE_BYTES', 1000)
        assert (await service.request('GET', '/status')).status == 502
        assert (await service.request('GET', '/status')).body['error']['code'] == 'bridgeproxy_redirect_rejected'
        assert (await service.request('GET', '/status')).body['error']['code'] == 'bridgeproxy_response_too_large'
        assert len(requests) == 4
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_transport_timeout_and_failure_do_not_retry_or_expose_exception(monkeypatch):
    calls = []
    def upstream(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ReadTimeout('private ' + READ_TOKEN, request=request)
        raise httpx.ConnectError('private ' + CONTROL_TOKEN, request=request)
    service = configured(monkeypatch, upstream)
    try:
        timeout = await service.request('POST', '/service/start')
        assert timeout.status == 504 and '结果未知' in timeout.body['error']['message']
        assert len(calls) == 1
        unavailable = await service.request('GET', '/status')
        assert unavailable.status == 503 and 'private' not in json.dumps(unavailable.body)
        assert len(calls) == 2
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('raw', [b'{"api_version":"v1","data":{"value":1e999}}',
                               b'{"api_version":"v1","data":{"value":"\\ud800"}}',
                               b'{"api_version":"v1","data":{"\\ud800":true}}'])
async def test_malformed_numeric_and_unicode_values_return_bounded_protocol_errors(monkeypatch, raw):
    service = configured(monkeypatch, lambda _: httpx.Response(200, content=raw,
                         headers={'Content-Type': 'application/json'}))
    try:
        result = await service.request('GET', '/status')
        assert result.status == 502 and result.body['error']['code'] == 'bridgeproxy_invalid_response'
    finally:
        await service.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('payload,status', [({'api_version': 'v1', 'error': 'invalid'}, 503),
                                          ({'api_version': 'v1', 'data': {'running': True}}, 503)])
async def test_error_responses_cannot_be_misrepresented_as_successful_state(monkeypatch, payload, status):
    service = configured(monkeypatch, lambda _: httpx.Response(status, json=payload))
    try:
        result = await service.request('GET', '/status')
        assert result.status == 502 and result.body['error']['code'] == 'bridgeproxy_invalid_response'
    finally:
        await service.close()


def test_registered_routes_and_matcher_use_the_shared_contract():
    registered = {(method, '/v1' + route.path.removeprefix('/api/bridgeproxy/v1').replace('{identifier}', '{id}'))
                  for route in router.routes for method in route.methods
                  if route.path != '/api/bridgeproxy/v1/adapter'}
    assert registered == {(row['method'], row['path']) for row in CONTRACT['routes']}
    for row in CONTRACT['routes']:
        path = row['path'][3:].replace('{id}', 'identifier_123')
        if path == '/pairings/control':
            continue
        assert allowed_route(row['method'], path), row
    for path in ('/http://other/', '/config?url=http://other', '/links/a%2fb', '/links/../config',
                 '/links/x/y', '/operations/abc#secret'):
        assert not allowed_route('GET', path) and not allowed_route('PATCH', path)


def test_api_auth_scopes_sas_separation_and_no_caller_transport_settings(monkeypatch):
    requests = []
    def upstream(request):
        requests.append(request)
        return core_reply({'running': False, 'pending': [{'verification_code': '12345678'}]})
    service = configured(monkeypatch, upstream)
    app = application(service)
    _, viewer = oidc_session(monkeypatch)
    with TestClient(app, base_url='https://app.example') as client:
        assert client.get('/api/bridgeproxy/v1/status').status_code == 401
        ordinary = client.get('/api/bridgeproxy/v1/pairings', headers=viewer)
        assert ordinary.status_code == 200 and 'verification_code' not in ordinary.text
        assert client.get('/api/bridgeproxy/v1/pairings/control', headers=viewer).status_code == 403
        assert client.post('/api/bridgeproxy/v1/service/start', headers=viewer, json={}).status_code == 403
        assert client.get('/api/bridgeproxy/v1/status?url=http://other&token=private', headers=viewer).status_code == 400
        assert len(requests) == 1
        _, admin = oidc_session(monkeypatch, 'admin')
        sas = client.get('/api/bridgeproxy/v1/pairings/control', headers=admin)
        assert sas.status_code == 200 and sas.json()['data']['pending'][0]['verification_code'] == '12345678'
        assert requests[-1].headers['Authorization'] == 'Bearer ' + CONTROL_TOKEN
        assert sas.headers['Cache-Control'] == 'no-store'
    asyncio.run(service.close())


@pytest.mark.asyncio
async def test_body_await_rechecks_revocation_before_privileged_dispatch(monkeypatch):
    requests = []
    service = configured(monkeypatch, lambda request: requests.append(request) or core_reply({}))
    session, headers = oidc_session(monkeypatch, 'admin')
    headers['Content-Type'] = 'application/json'
    async def body():
        yield b'{'
        identity.revoke_session(session['id'])
        yield b'}'
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(service)),
                                     base_url='https://app.example') as client:
            result = await client.post('/api/bridgeproxy/v1/service/start', headers=headers, content=body())
        assert result.status_code == 401 and not requests
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_sas_response_is_not_released_after_admin_session_revocation(monkeypatch):
    session, headers = oidc_session(monkeypatch, 'admin')
    def upstream(_):
        identity.revoke_session(session['id'])
        return core_reply({'pending': [{'verification_code': '12345678'}]})
    service = configured(monkeypatch, upstream)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=application(service)),
                                     base_url='https://app.example') as client:
            result = await client.get('/api/bridgeproxy/v1/pairings/control', headers=headers)
        assert result.status_code == 401 and '12345678' not in result.text
    finally:
        await service.close()


@pytest.mark.asyncio
async def test_missing_control_is_unavailable_without_using_read_token_for_writes(monkeypatch):
    calls = []
    service = configured(monkeypatch, lambda request: calls.append(request) or core_reply({}), control=False)
    try:
        assert not service.adapter().body['data']['control_configured']
        assert (await service.request('POST', '/service/start')).status == 503
        assert (await service.request('GET', '/pairings', control=True, allow_sas=True)).status == 503
        assert not calls
    finally:
        await service.close()
