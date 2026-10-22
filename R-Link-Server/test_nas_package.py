"""NAS release archives are immutable source, never a copy of a live checkout."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'scripts/build_nas_package.py'
REQUIRED = ['R-Link-Server/main.py', 'R-Link-Server/requirements.txt',
            'deploy/nas/requirements.lock', 'deploy/nas/compose.yaml',
            'deploy/nas/Dockerfile.server', 'deploy/nas/Dockerfile.web',
            'deploy/nas/nginx.conf', 'deploy/nas/.env.example',
            'deploy/nas/init.sh', 'deploy/nas/rlink.sh', 'deploy/nas/README.md',
            'apps/r-link-web/package.json', 'apps/r-link-web/package-lock.json',
            'apps/r-link-web/index.html', 'apps/r-link-web/vite.config.ts',
            'apps/r-link-web/tsconfig.json', 'apps/r-link-web/tsconfig.node.json',
            'apps/r-link-web/src/main.tsx']


def module():
    assert BUILDER.is_file(), 'Missing reproducible NAS package builder'
    spec = importlib.util.spec_from_file_location('nas_package', BUILDER)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def git(directory, *args):
    return subprocess.check_output(['git', '-C', str(directory), *args], text=True).strip()


@pytest.fixture
def repository(tmp_path):
    directory = tmp_path / 'source'
    directory.mkdir()
    git(directory, 'init', '-q')
    git(directory, 'config', 'user.name', 'Archive test')
    git(directory, 'config', 'user.email', 'archive@example.invalid')
    for name in REQUIRED + ['R-Link-Server/core/rfile.py', 'apps/r-link-web/src/App.tsx',
                            'deploy/nas/.env', 'R-Link-Server/config/private.json',
                            'R-Link-Server/core/__pycache__/secrets.pyc',
                            'R-Link-Server/builtin/demo/build/secret.py',
                            'apps/r-link-web/node_modules/secret.js',
                            'deploy/nas/server.key', 'deploy/nas/data/controller.json']:
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('DO_NOT_SHIP_SECRET' if 'secret' in name or name.endswith('.env') else name + '\n')
    git(directory, 'add', '.')
    git(directory, 'commit', '-qm', 'fixture')
    return directory


def test_source_archive_is_reproducible_and_uses_committed_blobs(repository, tmp_path):
    builder = module()
    first = builder.build_package(repository, 'HEAD', tmp_path / 'first', 'test-1')
    (repository / 'R-Link-Server/main.py').write_text('uncommitted runtime key')
    second = builder.build_package(repository, 'HEAD', tmp_path / 'second', 'test-1')
    assert first.read_bytes() == second.read_bytes()
    with tarfile.open(first) as archive:
        assert archive.extractfile('r-link-nas/R-Link-Server/main.py').read() == b'R-Link-Server/main.py\n'
        info = archive.getmember('r-link-nas/deploy/nas/init.sh')
        assert info.mode == 0o755 and info.uid == 0 and info.gid == 0
    assert first.with_suffix(first.suffix + '.sha256').read_text().startswith(hashlib.sha256(first.read_bytes()).hexdigest())


def test_archive_whitelist_excludes_tracked_and_untracked_runtime_data(repository, tmp_path):
    archive_path = module().build_package(repository, 'HEAD', tmp_path, 'test-1')
    with tarfile.open(archive_path) as archive:
        names = archive.getnames()
        assert all(not any(part in name for part in ('node_modules', '__pycache__', '/build/', '/data/', '/config/')) for name in names)
        assert 'r-link-nas/deploy/nas/.env' not in names
        assert 'r-link-nas/deploy/nas/server.key' not in names
        assert all(b'DO_NOT_SHIP_SECRET' not in archive.extractfile(item).read() for item in archive if item.isfile())
        manifest = json.load(archive.extractfile('r-link-nas/PACKAGE-MANIFEST.json'))
        assert manifest['source_commit'] == git(repository, 'rev-parse', 'HEAD')
        assert manifest['built_platforms'] == []
        assert manifest['source_build_platforms'] == ['linux/amd64', 'linux/arm64']
        for name in REQUIRED:
            assert name in manifest['files']
            assert manifest['files'][name] == hashlib.sha256(archive.extractfile('r-link-nas/' + name).read()).hexdigest()


def test_missing_dependency_lock_fails_without_partial_archive(repository, tmp_path):
    git(repository, 'rm', 'apps/r-link-web/package-lock.json')
    git(repository, 'commit', '-qm', 'missing lock')
    with pytest.raises(ValueError, match='package-lock'):
        module().build_package(repository, 'HEAD', tmp_path / 'output', 'test-1')
    assert not list((tmp_path / 'output').glob('*.tar.gz'))


def image_archive(path, *, architecture='amd64', token=False, revision=None):
    with tarfile.open(path, 'w') as archive:
        entries = []
        for role in ('server', 'web'):
            config = json.dumps({'architecture': architecture, 'os': 'linux', 'config': {
                'User': '10001' if role == 'server' else '',
                'Env': ['R_LINK_API_TOKEN=secret'] if token else ['PATH=/usr/bin'],
                'Labels': {'org.opencontainers.image.revision': revision},
                'Volumes': None}}).encode()
            name = role + '.json'
            info = tarfile.TarInfo(name)
            info.size = len(config)
            archive.addfile(info, io.BytesIO(config))
            entries.append({'Config': name, 'RepoTags': [f'rlink-nas-{role}:test-1'], 'Layers': []})
        data = json.dumps(entries).encode()
        info = tarfile.TarInfo('manifest.json')
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))


def test_offline_archive_records_actual_architecture_and_image_identity(repository, tmp_path):
    images = tmp_path / 'images.tar'
    image_archive(images, revision=git(repository, 'rev-parse', 'HEAD'))
    output = module().build_package(repository, 'HEAD', tmp_path / 'release', 'test-1', images)
    with tarfile.open(output) as archive:
        manifest = json.load(archive.extractfile('r-link-nas/PACKAGE-MANIFEST.json'))
        assert manifest['built_platforms'] == ['linux/amd64']
        assert len(manifest['images']) == 2
        assert manifest['files']['images.tar'] == hashlib.sha256(images.read_bytes()).hexdigest()
        assert archive.extractfile('r-link-nas/images.tar').read() == images.read_bytes()


@pytest.mark.parametrize('architecture,token,error', [('arm64', False, 'amd64'), ('amd64', True, 'secret')])
def test_offline_archive_rejects_wrong_platform_and_embedded_keys(repository, tmp_path, architecture, token, error):
    images = tmp_path / 'images.tar'
    image_archive(images, architecture=architecture, token=token)
    with pytest.raises(ValueError, match=error):
        module().build_package(repository, 'HEAD', tmp_path / 'release', 'test-1', images)


def test_offline_archive_rejects_images_from_a_different_source_commit(repository, tmp_path):
    images = tmp_path / 'images.tar'
    image_archive(images, revision='f' * 40)
    with pytest.raises(ValueError, match='source commit'):
        module().build_package(repository, 'HEAD', tmp_path / 'release', 'test-1', images)


def test_installation_generates_private_token_and_preserves_existing_key(tmp_path):
    import shutil
    candidate = Path('C:/Program Files/Git/bin/bash.exe')
    bash = str(candidate) if candidate.is_file() else shutil.which('bash')
    if not bash:
        pytest.skip('POSIX shell unavailable; run Linux installation tests')
    for name in ('init.sh', '.env.example'):
        shutil.copyfile(ROOT / 'deploy/nas' / name, tmp_path / name)
    script = str(tmp_path / 'init.sh').replace('\\', '/')
    first = subprocess.run([bash, script], capture_output=True, text=True, timeout=15)
    assert first.returncode == 0, first.stderr
    data = (tmp_path / '.env').read_bytes()
    token = next(line for line in data.decode().splitlines() if line.startswith('R_LINK_API_TOKEN=')).split('=', 1)[1]
    assert len(token) == 64 and all(char in '0123456789abcdef' for char in token)
    assert token not in first.stdout + first.stderr
    second = subprocess.run([bash, script], capture_output=True, text=True, timeout=15)
    assert second.returncode == 0, second.stderr
    assert (tmp_path / '.env').read_bytes() == data
    if __import__('os').name != 'nt':
        assert (tmp_path / '.env').stat().st_mode & 0o777 == 0o600


def test_installation_does_not_overwrite_an_invalid_existing_env(tmp_path):
    import shutil
    candidate = Path('C:/Program Files/Git/bin/bash.exe')
    bash = str(candidate) if candidate.is_file() else shutil.which('bash')
    if not bash:
        pytest.skip('POSIX shell unavailable')
    shutil.copyfile(ROOT / 'deploy/nas/init.sh', tmp_path / 'init.sh')
    data = b'R_LINK_API_TOKEN=\n'
    (tmp_path / '.env').write_bytes(data)
    result = subprocess.run([bash, str(tmp_path / 'init.sh').replace('\\', '/')], capture_output=True, text=True, timeout=15)
    assert result.returncode != 0
    assert (tmp_path / '.env').read_bytes() == data


def test_backup_rejects_existing_and_inside_release_destinations_before_mutation(tmp_path):
    import os
    import shutil
    candidate = Path('C:/Program Files/Git/bin/bash.exe')
    bash = str(candidate) if candidate.is_file() else shutil.which('bash')
    if not bash:
        pytest.skip('POSIX shell unavailable')
    release = tmp_path / 'release'
    nas = release / 'deploy/nas'
    nas.mkdir(parents=True)
    shutil.copyfile(ROOT / 'deploy/nas/rlink.sh', nas / 'rlink.sh')
    (nas / '.env').write_text('R_LINK_API_TOKEN=private-test-key\n')
    outside = tmp_path / 'existing'
    outside.mkdir()
    initial_mode = outside.stat().st_mode

    def shell_path(path):
        value = path.as_posix()
        return '/' + value[0].lower() + value[2:] if os.name == 'nt' else value

    for destination in (outside, release / 'new-backup'):
        result = subprocess.run([bash, str(nas / 'rlink.sh').replace('\\', '/'), 'backup', shell_path(destination)],
                                capture_output=True, text=True, timeout=15)
        assert result.returncode != 0
        assert outside.stat().st_mode == initial_mode
        assert not (release / 'new-backup').exists(), 'Backup must reject an inside-release path before mkdir/chmod/copy'


def test_nas_compose_has_private_api_auth_stable_retained_volumes_and_v1_schema():
    path = ROOT / 'deploy/nas/compose.yaml'
    assert path.is_file(), 'Missing DSM-compatible Compose installation'
    config = yaml.safe_load(path.read_text())
    assert config['version'] == '2.4'
    server = config['services']['server']
    assert 'ports' not in server
    assert ':?' in server['environment']['R_LINK_API_TOKEN']
    assert 'host.docker.internal:host-gateway' in server['extra_hosts']
    assert server['environment']['R_LINK_RFILE_URL'].endswith('http://host.docker.internal:18080}')
    assert all(value['name'].startswith('${R_LINK_VOLUME_PREFIX:-rlink-nas}') for value in config['volumes'].values())
    assert all(config['services'][name]['restart'] == 'unless-stopped' for name in ('server', 'web'))
    scripts = (ROOT / 'deploy/nas/rlink.sh').read_text()
    assert 'docker-compose' in scripts and 'docker compose' in scripts
    assert 'down -v' not in scripts and 'volume rm' not in scripts


def test_package_dockerfiles_do_not_bake_tokens_proxies_or_runtime_data():
    for name in ('server', 'web'):
        path = ROOT / f'deploy/nas/Dockerfile.{name}'
        assert path.is_file(), f'Missing {name} native Docker source'
        text = path.read_text()
        assert 'COPY . .' not in text
        assert 'R_LINK_API_TOKEN' not in text
        assert not any('PROXY' in line for line in text.splitlines() if line.startswith('ENV'))
    assert 'USER 10001' in (ROOT / 'deploy/nas/Dockerfile.server').read_text()


def test_install_docs_explain_credentials_retention_and_spk_limitations():
    path = ROOT / 'deploy/nas/README.md'
    assert path.is_file(), 'Missing installation and recovery instructions'
    text = path.read_text()
    for term in ('DS918+', 'DSM 7.1.1', 'apollolake', 'init.sh', 'load', 'backup',
                 'upgrade', 'uninstall', 'HTTPS', 'R_LINK_RFILE_SESSION_TOKEN',
                 'SPK', 'FROM_ENABLE_TO_POSTUNINST', 'FROM_POSTINST_TO_PREUNINST'):
        assert term in text


@pytest.mark.parametrize('configuration', ['template', 'compose-fallback'])
@pytest.mark.parametrize('origin,status', [('http://tauri.localhost', 200), ('tauri://localhost', 200),
                                          ('http://192.168.1.8:8080', 200), ('https://untrusted.example', 400)])
def test_nas_api_cors_preflight_keeps_desktop_and_appended_nas_origins(monkeypatch, configuration, origin, status):
    """Exercise the actual backend middleware with each shipped configuration."""
    from fastapi.testclient import TestClient

    if configuration == 'template':
        origins = next(line.split('=', 1)[1] for line in (ROOT / 'deploy/nas/.env.example').read_text().splitlines()
                       if line.startswith('R_LINK_CORS_ORIGINS='))
    else:
        compose = yaml.safe_load((ROOT / 'deploy/nas/compose.yaml').read_text())
        origins = compose['services']['server']['environment']['R_LINK_CORS_ORIGINS'].split(':-', 1)[1][:-1]
    # Operators append their NAS browser origin to the shipped desktop origins.
    monkeypatch.setenv('R_LINK_CORS_ORIGINS', origins + ',http://192.168.1.8:8080')
    monkeypatch.setenv('R_LINK_API_TOKEN', 'cors-regression-service-key')
    spec = importlib.util.spec_from_file_location('nas_preflight_main', ROOT / 'R-Link-Server/main.py')
    backend = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backend)
    with TestClient(backend.app) as client:
        response = client.options('/api/storage/upload?name=cors.txt', headers={
            'Origin': origin,
            'Access-Control-Request-Method': 'PUT',
            'Access-Control-Request-Headers': 'Authorization,Content-Type',
        })
        assert response.status_code == status, f'{configuration}: {origin}: {response.text}'
        if status == 200:
            assert response.headers['access-control-allow-origin'] == origin
            assert {'authorization', 'content-type'} <= {item.strip().lower() for item in response.headers['access-control-allow-headers'].split(',')}
            assert 'PUT' in response.headers['access-control-allow-methods']
            assert 'access-control-allow-credentials' not in response.headers
        else:
            assert 'access-control-allow-origin' not in response.headers
