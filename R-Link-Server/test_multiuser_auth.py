"""Protocol failure, role enforcement, session revocation and desktop handoff tests."""
import asyncio
import importlib.util
from pathlib import Path
import time
from urllib.parse import parse_qs, urlsplit, urlencode

import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException
from joserfc import jwt
from joserfc.jwk import RSAKey
from authlib.integrations.starlette_client import OAuth

from api import auth as auth_api
from core import identity
from core.auth import access_manager
from main import app


@pytest.fixture
def oidc(monkeypatch):
    monkeypatch.setenv('R_LINK_AUTH_MODE', 'oidc')
    monkeypatch.setenv('R_LINK_OIDC_ISSUER', 'https://id.example/realms/rlink')
    monkeypatch.setenv('R_LINK_OIDC_CLIENT_ID', 'rlink')
    monkeypatch.setenv('R_LINK_OIDC_CLIENT_SECRET', 'long-generated-client-secret')
    monkeypatch.setenv('R_LINK_PUBLIC_URL', 'https://app.example/r-link')
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    monkeypatch.delenv('R_LINK_BOOTSTRAP_ADMIN_SUBJECT', raising=False)
    client = TestClient(app, base_url='https://app.example', root_path='/r-link')
    yield client
    client.close()


def user_session(client, role='operator', subject='alice', kind='browser'):
    user = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': subject,
                                     'name': subject, 'email': 'same@example.test'})
    with identity.database() as db:
        db.execute('UPDATE users SET role=? WHERE id=?', (role, user['id']))
        user = dict(db.execute('SELECT * FROM users WHERE id=?', (user['id'],)).fetchone())
    current = identity.create_session(user, kind)
    if kind == 'browser':
        client.cookies.set(identity.SESSION_COOKIE, current['token'], domain='app.example', path='/r-link')
    return user, current


def mutation_headers(current, kind='browser'):
    result = {'X-R-Link-Session-Context': current['id']}
    if kind == 'browser':
        result.update({'X-R-Link-CSRF': current['csrf_token'], 'Origin': 'https://app.example'})
    else:
        result['Authorization'] = 'Bearer ' + current['token']
    return result


def test_oidc_never_trusts_local_peer_or_rauth_cookies(oidc):
    oidc.cookies.set('RAuth.session', 'pretend-admin')
    assert oidc.get('/r-link/api/auth/config').json()['mode'] == 'oidc'
    assert oidc.get('/r-link/api/auth/session').json()['authenticated'] is False
    assert oidc.get('/r-link/api/devices').status_code == 401


def test_oidc_cors_allows_configured_credentials_at_application_start(oidc):
    spec = importlib.util.spec_from_file_location('oidc_cors_app', Path(__file__).with_name('main.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with TestClient(module.app) as client:
        response = client.options('/api/auth/session', headers={
            'Origin': 'http://tauri.localhost', 'Access-Control-Request-Method': 'GET'})
        assert response.status_code == 200
        assert response.headers['Access-Control-Allow-Credentials'] == 'true'


@pytest.mark.parametrize('path', ['/api/plugins/x/config', '/api/plugins/x/logs', '/api/console/url',
                                  '/api/storage/download', '/api/rfile/download', '/api/downloads/x/file',
                                  '/api/ssh/connections', '/api/audit', '/api/mesh/setup-keys',
                                  '/api/system/processes', '/api/devices/export'])
def test_viewer_cannot_read_sensitive_endpoints(oidc, path):
    user_session(oidc, 'viewer')
    assert oidc.get('/r-link' + path).status_code == 403


def test_pending_and_viewer_are_enforced_on_http_and_ticket(oidc):
    _, current = user_session(oidc, 'pending')
    assert oidc.get('/r-link/api/auth/session').json()['user']['role'] == 'pending'
    assert oidc.get('/r-link/api/devices').status_code == 403
    user_session(oidc, 'viewer', 'bob')
    assert oidc.get('/r-link/api/devices').status_code == 200
    current = identity.read_session(oidc.cookies.get(identity.SESSION_COOKIE))
    assert oidc.post('/r-link/api/auth/ws-token', headers={
        'X-R-Link-CSRF': current['csrf'], 'X-R-Link-Session-Context': current['session_id'],
        'Origin': 'https://app.example'}).status_code == 403


@pytest.mark.parametrize('path,method', [('/api/auth/users', 'get'), ('/api/plugins/', 'get'),
                                       ('/api/console/url', 'get'), ('/api/audit', 'get'),
                                       ('/api/tunnels', 'get'), ('/api/tunnels', 'post'),
                                       ('/api/domains', 'get'), ('/api/mesh/setup-keys', 'get'),
                                       ('/api/devices/x/revoke', 'post'), ('/api/devices/x/link', 'post'),
                                       ('/api/mesh/groups', 'post'), ('/api/mesh/policies', 'post')])
def test_operator_cannot_use_administrative_routes(oidc, path, method):
    _, current = user_session(oidc)
    assert getattr(oidc, method)('/r-link' + path, headers=mutation_headers(current)).status_code == 403


def test_cookie_mutations_require_current_context_csrf_and_exact_origin(oidc):
    _, current = user_session(oidc)
    headers = mutation_headers(current)
    assert oidc.post('/r-link/api/auth/ws-token', headers=headers).status_code == 200
    for field, expected in [('X-R-Link-CSRF', 403), ('Origin', 403), ('X-R-Link-Session-Context', 409)]:
        bad = dict(headers)
        del bad[field]
        assert oidc.post('/r-link/api/auth/ws-token', headers=bad).status_code == expected
    headers['Origin'] = 'https://evil.example'
    assert oidc.post('/r-link/api/auth/ws-token', headers=headers).status_code == 403


def test_roles_bootstrap_by_exact_subject_not_email(oidc, monkeypatch):
    monkeypatch.setenv('R_LINK_BOOTSTRAP_ADMIN_SUBJECT', 'approved-subject')
    alice = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': 'approved-subject', 'email': 'a@b'})
    bob = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': 'new-subject', 'email': 'a@b'})
    assert alice['role'] == 'admin'
    assert bob['role'] == 'pending'
    assert alice['id'] != bob['id']
    with pytest.raises(HTTPException):
        identity.upsert_identity({'iss': 'https://evil.example', 'sub': 'approved-subject'})


def test_role_change_revokes_cookie_and_never_inherits_service_key(oidc, monkeypatch):
    user, current = user_session(oidc)
    monkeypatch.setenv('R_LINK_API_TOKEN', 'automation-secret')
    identity.update_user(user['id'], {'role': 'viewer'}, 'service-admin')
    assert oidc.get('/r-link/api/devices', headers={'Authorization': 'Bearer automation-secret'}).status_code == 401
    assert identity.read_session(current['token']) is None


def test_service_automation_does_not_become_a_browser_user(oidc, monkeypatch):
    monkeypatch.setenv('R_LINK_API_TOKEN', 'automation-secret')
    headers = {'Authorization': 'Bearer automation-secret'}
    response = oidc.get('/r-link/api/auth/session', headers=headers).json()
    assert response['authenticated'] is False and response['user'] is None
    assert oidc.get('/r-link/api/auth/users', headers=headers).status_code == 200


def test_admin_can_approve_users_and_cannot_remove_last_admin(oidc):
    admin, current = user_session(oidc, 'admin')
    pending = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': 'awaiting-approval'})
    users = oidc.get('/r-link/api/auth/users')
    assert users.status_code == 200 and len(users.json()['users']) == 2
    assert oidc.patch('/r-link/api/auth/users/' + pending['id'], json={'role': 'operator'},
                      headers=mutation_headers(current)).status_code == 200
    assert oidc.patch('/r-link/api/auth/users/' + admin['id'], json={'disabled': True},
                      headers=mutation_headers(current)).status_code == 409


@pytest.mark.asyncio
async def test_ssh_tickets_are_single_use_and_follow_session_revocation(oidc):
    user, current = user_session(oidc)
    session = identity.read_session(current['token'])
    session['principal'] = 'user'
    token = await access_manager.issue_websocket_token(session, scope='ssh')
    claims = await access_manager.verify_websocket_token(token, expected_scope='ssh')
    assert claims and access_manager.websocket_identity_valid(claims)
    assert await access_manager.verify_websocket_token(token, expected_scope='ssh') is None
    stale = await access_manager.issue_websocket_token(session, scope='ssh')
    identity.update_user(user['id'], {'role': 'viewer'}, 'admin')
    assert await access_manager.verify_websocket_token(stale, expected_scope='ssh') is None
    assert not access_manager.websocket_identity_valid(claims)


def test_logout_revokes_cookie_and_prevents_ongoing_callback(oidc):
    _, current = user_session(oidc)
    with identity.database() as db:
        db.execute('INSERT INTO flows(state,binding,nonce,verifier,expires_at,used,parent_session) VALUES (?,?,?,?,?,1,?)',
                   ('ongoing', identity.digest('binding'), 'nonce', 'verifier', int(time.time()) + 300, current['id']))
    response = oidc.post('/r-link/api/auth/logout', headers=mutation_headers(current))
    assert response.status_code == 204
    assert identity.read_session(current['token']) is None
    with identity.database() as db:
        assert not db.execute('SELECT * FROM flows').fetchall()


def test_old_browser_logout_revokes_rotated_new_account_session(oidc):
    user, old = user_session(oidc)
    bob = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': 'bob'})
    with identity.database() as db:
        replacement = identity.create_session_in_db(db, bob['id'], parent_session=old['id'])
    assert identity.read_session(old['token']) is None
    # A logout already sent with the former CSRF/context must revoke the entire browser family.
    response = oidc.post('/r-link/api/auth/logout', headers=mutation_headers(old))
    assert response.status_code == 204
    assert identity.read_session(replacement['token']) is None


def test_stale_tab_cannot_start_independent_login_family(oidc, provider):
    _, old = user_session(oidc)
    bob = identity.upsert_identity({'iss': identity.settings()['issuer'], 'sub': 'bob'})
    with identity.database() as db:
        identity.create_session_in_db(db, bob['id'], parent_session=old['id'])
    response = oidc.get('/r-link/api/auth/login', follow_redirects=False)
    assert response.status_code == 409
    with identity.database() as db:
        assert not db.execute('SELECT * FROM flows').fetchall()


def test_console_fails_closed_in_multiuser_mode(oidc):
    _, current = user_session(oidc, 'admin')
    for path in ('start', 'restart'):
        assert oidc.post('/r-link/api/console/' + path, headers=mutation_headers(current)).status_code == 503
    assert oidc.get('/r-link/api/console/url').status_code == 503


class FakeProvider:
    claims = None
    verification_error = False

    async def create_authorization_url(self, callback, **kwargs):
        self.parameters = kwargs
        return {'url': 'https://id.example/authorize?' + urlencode(kwargs)}

    async def fetch_access_token(self, **kwargs):
        assert kwargs['code_verifier'] == self.parameters['code_verifier']
        assert kwargs['redirect_uri'] == 'https://app.example/r-link/api/auth/callback'
        return {'id_token': 'not-persisted', 'access_token': 'not-persisted-either'}

    async def parse_id_token(self, token, **kwargs):
        if self.verification_error:
            raise ValueError('Invalid signed ID token')
        return self.claims or {'iss': identity.settings()['issuer'], 'sub': 'alice', 'nonce': kwargs['nonce'], 'aud': 'rlink'}


@pytest.fixture
def provider(monkeypatch):
    remote = FakeProvider()
    async def create():
        return remote
    monkeypatch.setattr(auth_api, 'oidc_client', create)
    return remote


def browser_login(client):
    response = client.get('/r-link/api/auth/login', follow_redirects=False)
    assert response.status_code == 302
    query = parse_qs(urlsplit(response.headers['location']).query)
    return query['state'][0]


def test_callback_is_browser_bound_single_use_and_token_free(oidc, provider):
    state = browser_login(oidc)
    with identity.database() as db:
        flow = db.execute('SELECT * FROM flows').fetchone()
        assert flow['state'] == identity.digest(state)
        assert provider.parameters['code_verifier'] not in flow['verifier']
    unbound = TestClient(app, base_url='https://app.example', root_path='/r-link')
    assert unbound.get('/r-link/api/auth/callback', params={'state': state, 'code': 'x'}).status_code == 400
    unbound.close()
    response = oidc.get('/r-link/api/auth/callback', params={'state': state, 'code': 'x'}, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers['location'] == 'https://app.example/r-link/'
    cookie = response.headers['set-cookie']
    assert 'HttpOnly' in cookie and 'Secure' in cookie and 'Path=/r-link' in cookie and 'SameSite=lax' in cookie
    assert oidc.get('/r-link/api/auth/session').json()['authenticated'] is True
    assert oidc.get('/r-link/api/auth/callback', params={'state': state, 'code': 'x'}).status_code == 400
    with identity.database() as db:
        assert not db.execute('SELECT * FROM flows').fetchall()
        dump = ''.join(db.iterdump())
        assert 'not-persisted' not in dump


@pytest.mark.parametrize('failure', ['nonce', 'signature', 'provider-error', 'expired'])
def test_oidc_callback_fails_closed(oidc, provider, failure):
    state = browser_login(oidc)
    if failure == 'nonce':
        provider.claims = {'iss': identity.settings()['issuer'], 'sub': 'alice', 'nonce': 'wrong'}
    if failure == 'signature':
        provider.verification_error = True
    if failure == 'expired':
        with identity.database() as db:
            db.execute('UPDATE flows SET expires_at=0')
    params = {'state': state, 'code': 'x'}
    if failure == 'provider-error':
        params['error'] = 'access_denied'
    assert oidc.get('/r-link/api/auth/callback', params=params).status_code == 400
    assert oidc.get('/r-link/api/auth/session').json()['authenticated'] is False


def test_logout_during_token_exchange_cannot_restore_browser_session(oidc, provider, monkeypatch):
    _, current = user_session(oidc)
    state = browser_login(oidc)
    original_exchange = provider.fetch_access_token
    async def exchange_after_logout(**kwargs):
        identity.revoke_session(current['id'])
        return await original_exchange(**kwargs)
    monkeypatch.setattr(provider, 'fetch_access_token', exchange_after_logout)
    response = oidc.get('/r-link/api/auth/callback', params={'state': state, 'code': 'x'})
    assert response.status_code == 400
    assert oidc.get('/r-link/api/auth/session').json()['authenticated'] is False
    with identity.database() as db:
        assert not db.execute('SELECT * FROM sessions').fetchall()


def test_desktop_exchange_requires_secret_is_single_use_and_no_return_url(oidc, provider):
    data = oidc.post('/r-link/api/auth/desktop/start', headers={'Origin': 'http://tauri.localhost'}).json()
    assert data['poll_secret'] not in data['login_url']
    body = {'flow_id': data['flow_id'], 'poll_secret': data['poll_secret']}
    assert oidc.post('/r-link/api/auth/desktop/exchange', json=body).status_code == 202
    bad = dict(body, poll_secret='wrong' * 10)
    assert oidc.post('/r-link/api/auth/desktop/exchange', json=bad).status_code == 400
    response = oidc.get(data['login_url'], follow_redirects=False)
    state = parse_qs(urlsplit(response.headers['location']).query)['state'][0]
    assert oidc.get('/r-link/api/auth/callback', params={'state': state, 'code': 'x'}).status_code == 200
    exchanged = oidc.post('/r-link/api/auth/desktop/exchange', json=body)
    assert exchanged.status_code == 200
    token = exchanged.json()['token']
    assert identity.read_session(token)['kind'] == 'desktop'
    assert oidc.post('/r-link/api/auth/desktop/exchange', json=body).status_code == 400
    assert oidc.post('/r-link/api/auth/desktop/start', headers={'Origin': 'https://evil.example'}).status_code == 403


def test_expired_desktop_exchange_is_rejected(oidc):
    data = oidc.post('/r-link/api/auth/desktop/start').json()
    with identity.database() as db:
        db.execute('UPDATE desktop_flows SET expires_at=0')
    assert oidc.post('/r-link/api/auth/desktop/exchange', json={
        'flow_id': data['flow_id'], 'poll_secret': data['poll_secret']}).status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize('wrong', ['iss', 'aud', 'aud-with-azp', 'nonce', 'exp', 'signature'])
async def test_authlib_rejects_invalid_signed_id_tokens(oidc, monkeypatch, wrong):
    key = RSAKey.generate_key(2048)
    key.ensure_kid()
    remote = OAuth().register('test', client_id='rlink')
    metadata = {'issuer': identity.settings()['issuer'], 'id_token_signing_alg_values_supported': ['RS256']}
    async def load():
        return metadata
    async def jwks(**kwargs):
        return {'keys': [key.as_dict()]}
    monkeypatch.setattr(remote, 'load_server_metadata', load)
    monkeypatch.setattr(remote, 'fetch_jwk_set', jwks)
    claims = {'iss': identity.settings()['issuer'], 'sub': 'alice', 'aud': 'rlink', 'nonce': 'nonce',
              'iat': int(time.time()), 'exp': int(time.time()) + 300}
    if wrong in {'iss', 'aud', 'nonce'}:
        claims[wrong] = 'wrong'
    if wrong == 'exp':
        claims['exp'] = int(time.time()) - 60
    if wrong == 'aud-with-azp':
        claims['aud'] = 'another-client'
        claims['azp'] = 'rlink'
    signing_key = RSAKey.generate_key(2048) if wrong == 'signature' else key
    token = jwt.encode({'alg': 'RS256', 'kid': key.as_dict()['kid']}, claims, signing_key)
    with pytest.raises(Exception):
        await remote.parse_id_token({'id_token': token, 'access_token': 'temporary'}, nonce='nonce', leeway=0,
                                    claims_options={'iss': {'essential': True, 'value': identity.settings()['issuer']},
                                                    'aud': {'essential': True, 'value': 'rlink'}})
