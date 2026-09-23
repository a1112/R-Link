"""Durable service data and a single-owner lock for background work."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import uuid

from fastapi import HTTPException
from core.paths import SERVER_DIR


def now():
    return datetime.now(timezone.utc).isoformat()


class ServiceState:
    def __init__(self, root=None):
        self.root = Path(root or os.getenv('R_LINK_DATA_DIR', str(SERVER_DIR / 'data'))).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = self.root / 'services.sqlite3'
        self.lock_file = None
        with self.db() as db:
            db.execute('PRAGMA journal_mode=WAL')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 1:
                raise RuntimeError('Service database is newer than this server')
            db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, data TEXT NOT NULL, PRIMARY KEY(kind,id))')
            db.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, at TEXT, action TEXT, resource TEXT)')
            db.execute('PRAGMA user_version=1')
        if os.name != 'nt':
            self.path.chmod(0o600)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def acquire(self):
        self.lock_file = (self.root / 'worker.lock').open('a+b')
        try:
            self.lock_file.seek(0)
            if os.name == 'nt':
                import msvcrt
                if not self.lock_file.read(1):
                    self.lock_file.write(b'0')
                    self.lock_file.flush()
                self.lock_file.seek(0)
                msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.lock_file.close()
            self.lock_file = None
            raise RuntimeError('R-Link background services require one worker per R_LINK_DATA_DIR') from None

    def release(self):
        if self.lock_file:
            self.lock_file.close()
            self.lock_file = None

    def list(self, kind):
        with self.db() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT data FROM records WHERE kind=? ORDER BY rowid', (kind,))]

    def get(self, kind, identifier):
        with self.db() as db:
            row = db.execute('SELECT data FROM records WHERE kind=? AND id=?', (kind, identifier)).fetchone()
        if row is None:
            raise HTTPException(404, '记录不存在')
        return json.loads(row[0])

    def save(self, kind, data, identifier=None):
        item = dict(data, id=identifier or str(uuid.uuid4()), updated_at=now())
        with self.db() as db:
            db.execute('INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET data=excluded.data',
                       (kind, item['id'], json.dumps(item, ensure_ascii=False)))
        return item

    def delete(self, kind, identifier):
        self.get(kind, identifier)
        with self.db() as db:
            db.execute('DELETE FROM records WHERE kind=? AND id=?', (kind, identifier))

    def audit(self, action, resource):
        with self.db() as db:
            db.execute('INSERT INTO audit(at,action,resource) VALUES (?,?,?)', (now(), action, resource))
            db.execute('DELETE FROM audit WHERE id <= (SELECT COALESCE(MAX(id),0)-5000 FROM audit)')

    def events(self):
        with self.db() as db:
            return [dict(zip(('id', 'at', 'action', 'resource'), row)) for row in
                    db.execute('SELECT id,at,action,resource FROM audit ORDER BY id DESC LIMIT 200')]
