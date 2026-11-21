"""R-Auth browser sessions bound to R-Link's own role, revision and CSRF context."""
from functools import lru_cache
import os
import secrets
import time
import uuid
from fastapi import HTTPException
from core import identity


def enabled():
    return os.getenv('R_LINK_AUTH_MODE', '').lower() == 'r-auth'


@lru_cache(maxsize=1)
def store():
    from r_auth_session import ProjectSessions
    return ProjectSessions('r-link')


def call(operation, proofs):
    from r_auth_session import SessionUnavailable
    try:
        return getattr(store(), operation)(proofs)
    except SessionUnavailable:
        raise HTTPException(503, 'R-Auth unavailable') from None


def user_for(claims, proofs):
    if not claims:
        return None
    session_id = 'r-auth:' + claims['id']
    with identity.database() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM users WHERE issuer=? AND subject=?', (claims['issuer'], claims['subject'])).fetchone()
        if not row:
            role = 'admin' if claims['subject'] == os.getenv('R_LINK_BOOTSTRAP_ADMIN_SUBJECT') else 'pending'
            now = int(time.time())
            db.execute('INSERT INTO users(id,issuer,subject,display_name,role,created_at,last_login) VALUES(?,?,?,?,?,?,?)',
                       (str(uuid.uuid4()), claims['issuer'], claims['subject'], claims['subject'], role, now, now))
            row = db.execute('SELECT * FROM users WHERE issuer=? AND subject=?', (claims['issuer'], claims['subject'])).fetchone()
        if row['disabled']:
            raise HTTPException(403, 'User is disabled')
        db.execute('''INSERT INTO central_sessions(id,user_id,revision,csrf,browser_hash,session_hash,expires_at)
                      VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO NOTHING''',
                   (session_id, row['id'], row['revision'], secrets.token_urlsafe(32),
                    proofs['browserHash'], proofs['sessionHash'], claims['expires_at']))
        binding = db.execute('SELECT * FROM central_sessions WHERE id=?', (session_id,)).fetchone()
        if (binding['revoked'] or binding['revision'] != row['revision'] or binding['user_id'] != row['id']
                or binding['browser_hash'] != proofs['browserHash'] or binding['session_hash'] != proofs['sessionHash']):
            return None
        return dict(row) | {'session_id': session_id, 'kind': 'browser', 'expires_at': binding['expires_at'], 'csrf': binding['csrf']}


def browser(request):
    proofs = store().proofs(request.headers.getlist('cookie'))
    return user_for(call('current', proofs), proofs)


def stored_proofs(session_id):
    with identity.database() as db:
        row = db.execute('SELECT * FROM central_sessions WHERE id=? AND revoked=0', (session_id,)).fetchone()
        return {'browserHash': row['browser_hash'], 'sessionHash': row['session_hash']} if row else None


def active(session_id):
    proofs = stored_proofs(session_id)
    claims = call('current', proofs)
    if claims and session_id == 'r-auth:' + claims['id']:
        return user_for(claims, proofs)
    return None


def logout(session_id):
    proofs = stored_proofs(session_id)
    if proofs:
        call('logout', proofs)
        with identity.database() as db:
            db.execute('UPDATE central_sessions SET revoked=1 WHERE id=?', (session_id,))
