from io import BytesIO
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from core import storage
from main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_STORAGE_DIR', str(tmp_path / 'shared'))
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    with TestClient(app, base_url='http://localhost:8210', client=('127.0.0.1', 55555)) as client:
        yield client


def test_shared_file_round_trip_and_empty_directory_rules(client):
    assert client.get('/api/storage').json()['entries'] == []
    assert client.post('/api/storage/directory', json={'path': '', 'name': '项目文件'}).status_code == 201
    payload = '真实内容\nhello'.encode()
    params = {'path': '项目文件', 'name': '说明.txt'}
    uploaded = client.put('/api/storage/upload', params=params, content=payload)
    assert uploaded.status_code == 201
    assert uploaded.json()['size'] == len(payload)
    listing = client.get('/api/storage', params={'path': '项目文件'}).json()
    assert listing['entries'][0]['name'] == '说明.txt'
    response = client.get('/api/storage/download', params={'path': '项目文件/说明.txt'})
    assert response.content == payload
    assert response.headers['content-type'] == 'application/octet-stream'
    assert response.headers['content-disposition'].startswith("attachment;")
    assert client.put('/api/storage/upload', params=params, content=b'overwrite').status_code == 409
    assert client.get('/api/storage/download', params={'path': '项目文件/说明.txt'}).content == payload
    assert client.delete('/api/storage', params={'path': '项目文件'}).status_code == 409
    renamed = client.post('/api/storage/rename', json={'path': '项目文件/说明.txt', 'name': 'new.txt'})
    assert renamed.status_code == 200
    assert client.delete('/api/storage', params={'path': '项目文件/new.txt'}).status_code == 204
    assert client.delete('/api/storage', params={'path': '项目文件'}).status_code == 204
    assert client.get('/api/storage').json()['entries'] == []


@pytest.mark.parametrize('path', ['../outside', '/etc', 'C:/Windows', 'folder/../outside', 'folder\\outside', 'CON', 'file.txt:stream', 'foo.', 'foo ', '.rlink-upload-evil'])
def test_unsafe_paths_cannot_read_write_rename_or_delete(client, path):
    assert client.get('/api/storage', params={'path': path}).status_code in (400, 404)
    assert client.put('/api/storage/upload', params={'name': path}, content=b'bad').status_code == 400
    assert client.delete('/api/storage', params={'path': path}).status_code in (400, 404)
    assert client.post('/api/storage/directory', json={'name': path}).status_code == 400


def test_upload_limit_empty_files_and_root_protection(client, monkeypatch):
    monkeypatch.setattr(storage, 'MAX_FILE_BYTES', 4)
    assert client.put('/api/storage/upload', params={'name': 'too-large'}, content=b'12345').status_code == 413
    assert client.get('/api/storage').json()['entries'] == []
    assert client.put('/api/storage/upload', params={'name': 'empty'}, content=b'').status_code == 201
    assert client.get('/api/storage/download', params={'path': 'empty'}).content == b''
    assert client.delete('/api/storage', params={'path': ''}).status_code == 400
    assert client.post('/api/storage/rename', json={'path': '', 'name': 'moved'}).status_code == 400


def test_authentication_precedes_shared_folder_access(tmp_path, monkeypatch):
    monkeypatch.setenv('R_LINK_STORAGE_DIR', str(tmp_path / 'private'))
    monkeypatch.delenv('R_LINK_API_TOKEN', raising=False)
    with TestClient(app) as remote:
        assert remote.get('/api/storage').status_code == 401
        assert remote.put('/api/storage/upload', params={'name': 'a'}, content=b'a').status_code == 401
        assert remote.get('/api/storage/download', params={'path': 'a'}).status_code == 401
        assert remote.delete('/api/storage', params={'path': 'a'}).status_code == 401
    assert not (tmp_path / 'private').exists()


def test_service_key_and_cross_origin_protection(client, monkeypatch):
    assert client.get('/api/storage', headers={'Origin': 'https://evil.invalid'}).status_code == 401
    monkeypatch.setenv('R_LINK_API_TOKEN', 'test-only-key')
    assert client.get('/api/storage').status_code == 401
    assert client.get('/api/storage', headers={'Authorization': 'Bearer test-only-key'}).status_code == 200


def test_hardlinked_external_file_is_not_exposed(client, tmp_path):
    outside = tmp_path / 'outside.txt'
    outside.write_bytes(b'private')
    root = storage.root()
    os.link(outside, root / 'linked')
    assert client.get('/api/storage').json()['skipped'] == 1
    assert client.get('/api/storage/download', params={'path': 'linked'}).status_code == 403
    assert client.delete('/api/storage', params={'path': 'linked'}).status_code == 403
    assert outside.read_bytes() == b'private'


def test_symlink_directory_cannot_escape_shared_root(client, tmp_path):
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'secret').write_bytes(b'private')
    try:
        (storage.root() / 'link').symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Symlink creation is not available on this host')
    assert client.get('/api/storage', params={'path': 'link'}).status_code == 403
    assert client.get('/api/storage/download', params={'path': 'link/secret'}).status_code == 403
    assert client.put('/api/storage/upload', params={'path': 'link', 'name': 'new'}, content=b'x').status_code == 403
    assert not (outside / 'new').exists()


def test_concurrent_upload_never_overwrites_existing_content(client):
    def write(data):
        try:
            storage.store_file('', 'same.txt', BytesIO(data))
            return 201
        except HTTPException as error:
            return error.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(write, [b'first', b'second']))
    assert sorted(outcomes) == [201, 409]
    assert (storage.root() / 'same.txt').read_bytes() in (b'first', b'second')
    assert list(storage.root().glob('.rlink-upload-*')) == []


def test_rename_does_not_overwrite_other_files(client):
    for name in ['a', 'b']:
        client.put('/api/storage/upload', params={'name': name}, content=name.encode())
    assert client.post('/api/storage/rename', json={'path': 'a', 'name': 'b'}).status_code == 409
    assert client.get('/api/storage/download', params={'path': 'b'}).content == b'b'
