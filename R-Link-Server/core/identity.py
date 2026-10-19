"""R-Link-owned identities and opaque sessions; IdP tokens are never persisted."""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import base64
import os
import secrets
import sqlite3
import threading
import time
import uuid
from urllib.parse import urlsplit

from fastapi import HTTPException
from cryptography.fernet import Fernet
from core.paths import CONFIG_DIR

ROLES = {'pending': 0, 'viewer': 1, 'operator': 2, 'admin': 3}
DB_LOCK = threading.RLock()


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def flow_cipher() -> Fernet:
    secret = os.getenv('R_LINK_AUTH_FLOW_SECRET') or settings()['client_secret']
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(('R-Link OIDC flow v1:' + secret).encode()).digest()))


def encrypt_flow(value: str) -> str:
    return flow_cipher().encrypt(value.encode()).decode()


def decrypt_flow(value: str) -> str:
    return flow_cipher().decrypt(value.encode(), ttl=300).decode()


def enabled() -> bool:
    return os.getenv('R_LINK_AUTH_MODE', '').lower() == 'oidc' or bool(os.getenv('R_LINK_OIDC_ISSUER'))


def mode() -> str:
    return 'oidc' if enabled() else ('service' if os.getenv('R_LINK_API_TOKEN') else 'local')


def settings() -> dict:
    issuer = os.getenv('R_LINK_OIDC_ISSUER', '')
    public_url = os.getenv('R_LINK_PUBLIC_URL', '').rstrip('/')
    client_id = os.getenv('R_LINK_OIDC_CLIENT_ID', '')
    client_secret = os.getenv('R_LINK_OIDC_CLIENT_SECRET', '')
    for name, value in [('issuer', issuer), ('public URL', public_url)]:
        parsed = urlsplit(value)
        if (any(ord(char) <= 32 or char == '\\' for char in value)
                or parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment):
            raise HTTPException(503, f'OIDC {name} must be a configured HTTPS URL')
    if not client_id or not client_secret:
        raise HTTPException(503, 'OIDC client is not configured')
    return {'issuer': issuer, 'public_url': public_url, 'client_id': client_id,
            'client_secret': client_secret, 'callback': public_url + '/api/auth/callback'}


def configured() -> bool:
    if not enabled():
        return False
    try:
        settings()
        return True
    except HTTPException:
        return False


def cookie_settings() -> dict:
    config = settings()
    return {'path': urlsplit(config['public_url']).path.rstrip('/') or '/',
            'secure': True, 'httponly': True, 'samesite': 'lax'}


SESSION_COOKIE = '__Secure-r_link_session'
FLOW_COOKIE = '__Secure-r_link_login'


@contextmanager
def database():
    path = Path(os.getenv('R_LINK_AUTH_DB', str(CONFIG_DIR / 'auth.sqlite3')))
    path.parent.mkdir(parents=True, exist_ok=True)
    with DB_LOCK:
        connection = sqlite3.connect(path, timeout=10)
        os.chmod(path, 0o600)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.executescript('''
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY, issuer TEXT NOT NULL, subject TEXT NOT NULL,
                        display_name TEXT NOT NULL, email TEXT, role TEXT NOT NULL,
                        disabled INTEGER NOT NULL DEFAULT 0, revision INTEGER NOT NULL DEFAULT 1,
                        created_at INTEGER NOT NULL, last_login INTEGER NOT NULL,
                        UNIQUE(issuer, subject));
                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, revision INTEGER NOT NULL,
                        csrf TEXT NOT NULL, kind TEXT NOT NULL, expires_at INTEGER NOT NULL,
                        family TEXT NOT NULL, current INTEGER NOT NULL DEFAULT 1);
                    CREATE TABLE IF NOT EXISTS flows (
                        state TEXT PRIMARY KEY, binding TEXT NOT NULL, nonce TEXT NOT NULL,
                        verifier TEXT NOT NULL, desktop_id TEXT, expires_at INTEGER NOT NULL,
                        used INTEGER NOT NULL DEFAULT 0, parent_session TEXT);
                    CREATE TABLE IF NOT EXISTS desktop_flows (
                        id TEXT PRIMARY KEY, secret TEXT NOT NULL, user_id TEXT,
                        expires_at INTEGER NOT NULL, started INTEGER NOT NULL DEFAULT 0);
                    CREATE TABLE IF NOT EXISTS websocket_uses (
                        nonce TEXT PRIMARY KEY, expires_at INTEGER NOT NULL);
                    CREATE TABLE IF NOT EXISTS auth_audit (
                        id INTEGER PRIMARY KEY, actor TEXT NOT NULL, target TEXT NOT NULL,
                        action TEXT NOT NULL, created_at INTEGER NOT NULL);
                ''')
                current = int(time.time())
                for table in ('sessions', 'flows', 'desktop_flows', 'websocket_uses'):
                    connection.execute(f'DELETE FROM {table} WHERE expires_at <= ?', (current,))
            with connection:
                yield connection
        finally:
            connection.close()


def public_user(row) -> dict:
    return {key: bool(row[key]) if key == 'disabled' else row[key]
            for key in ('id', 'issuer', 'subject', 'display_name', 'email', 'role', 'disabled',
                        'created_at', 'last_login')}


def upsert_identity(claims: dict) -> dict:
    issuer, subject = claims.get('iss'), claims.get('sub')
    if issuer != settings()['issuer'] or not isinstance(subject, str) or not subject:
        raise HTTPException(401, 'Invalid provider identity')
    current = int(time.time())
    # Exact trusted issuer+subject bootstrap only. Email is display metadata.
    role = 'admin' if subject == os.getenv('R_LINK_BOOTSTRAP_ADMIN_SUBJECT') else 'pending'
    name = str(claims.get('name') or claims.get('preferred_username') or subject)[:200]
    email = str(claims.get('email') or '')[:320] or None
    with database() as db:
        db.execute('''INSERT INTO users (id,issuer,subject,display_name,email,role,created_at,last_login)
                      VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(issuer,subject) DO UPDATE SET
                      display_name=excluded.display_name,email=excluded.email,last_login=excluded.last_login''',
                   (str(uuid.uuid4()), issuer, subject, name, email, role, current, current))
        row = db.execute('SELECT * FROM users WHERE issuer=? AND subject=?', (issuer, subject)).fetchone()
        if row['disabled']:
            raise HTTPException(403, 'User is disabled')
        return dict(row)


def create_session(user: dict, kind='browser') -> dict:
    with database() as db:
        return create_session_in_db(db, user['id'], kind)


def create_session_in_db(db, user_id: str, kind='browser', parent_session=None) -> dict:
    token = secrets.token_urlsafe(48)
    try:
        ttl = max(300, min(28800, int(os.getenv('R_LINK_SESSION_SECONDS', '28800'))))
    except ValueError:
        raise HTTPException(503, 'Invalid session lifetime configuration')
    csrf = secrets.token_urlsafe(32)
    expires = int(time.time()) + ttl
    # Re-read, so role changes between OIDC completion and exchange cannot revive a session.
    row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
    if not row or row['disabled']:
        raise HTTPException(403, 'User is disabled')
    family = secrets.token_urlsafe(32)
    if parent_session:
        parent = db.execute('SELECT * FROM sessions WHERE id=? AND current=1', (parent_session,)).fetchone()
        if not parent:
            raise HTTPException(400, 'Login was cancelled by a session change')
        family = parent['family']
        db.execute('UPDATE sessions SET current=0 WHERE family=?', (family,))
    db.execute('INSERT INTO sessions VALUES (?,?,?,?,?,?,?,1)',
               (digest(token), row['id'], row['revision'], csrf, kind, expires, family))
    return {'token': token, 'id': digest(token), 'csrf_token': csrf, 'expires_at': expires}


def session_from_hash(session_id: str, *, allow_retired=False) -> dict | None:
    with database() as db:
        row = db.execute('''SELECT users.*, sessions.id AS session_id, sessions.csrf,
                           sessions.expires_at, sessions.kind, sessions.family, sessions.current,
                           sessions.revision AS session_revision
                           FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.id=?''',
                         (session_id,)).fetchone()
        if (not row or (not allow_retired and not row['current'])
                or row['disabled'] or row['revision'] != row['session_revision']
                or row['issuer'] != settings()['issuer']):
            return None
        return dict(row)


def read_session(token: str, *, allow_retired=False) -> dict | None:
    return session_from_hash(digest(token), allow_retired=allow_retired) if token and len(token) <= 256 else None


def revoke_session(session_id: str):
    with database() as db:
        row = db.execute('SELECT family FROM sessions WHERE id=?', (session_id,)).fetchone()
        if row:
            db.execute('DELETE FROM flows WHERE parent_session IN (SELECT id FROM sessions WHERE family=?)', (row['family'],))
            db.execute('DELETE FROM sessions WHERE family=?', (row['family'],))


def list_users() -> list[dict]:
    with database() as db:
        return [public_user(row) for row in db.execute('SELECT * FROM users ORDER BY created_at,id')]


def update_user(user_id: str, changes: dict, actor: str) -> dict:
    with database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'User not found')
        role = changes.get('role', row['role'])
        disabled = changes.get('disabled', bool(row['disabled']))
        if row['role'] == 'admin' and not row['disabled'] and (role != 'admin' or disabled):
            count = db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND disabled=0").fetchone()[0]
            if count <= 1:
                raise HTTPException(409, 'The last active administrator cannot be removed')
        db.execute('UPDATE users SET role=?,disabled=?,revision=revision+1 WHERE id=?',
                   (role, int(disabled), user_id))
        db.execute('DELETE FROM sessions WHERE user_id=?', (user_id,))
        db.execute('INSERT INTO auth_audit(actor,target,action,created_at) VALUES (?,?,?,?)',
                   (actor, user_id, f'role={role};disabled={disabled}', int(time.time())))
        return public_user(db.execute('SELECT * FROM users WHERE id=?', (user_id,)).fetchone())


def consume_websocket_nonce(nonce: str, expires: int) -> bool:
    try:
        with database() as db:
            db.execute('INSERT INTO websocket_uses VALUES (?,?)', (nonce, expires))
        return True
    except sqlite3.IntegrityError:
        return False
