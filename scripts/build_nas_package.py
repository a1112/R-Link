#!/usr/bin/env python3
"""Reproducible NAS source/offline releases from committed, whitelisted Git blobs."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile

REQUIRED = {'R-Link-Server/main.py', 'R-Link-Server/requirements.txt',
            'deploy/nas/requirements.lock', 'deploy/nas/compose.yaml',
            'deploy/nas/Dockerfile.server', 'deploy/nas/Dockerfile.web',
            'deploy/nas/nginx.conf', 'deploy/nas/.env.example',
            'deploy/nas/init.sh', 'deploy/nas/rlink.sh', 'deploy/nas/README.md',
            'apps/r-link-web/package.json', 'apps/r-link-web/package-lock.json',
            'apps/r-link-web/index.html', 'apps/r-link-web/vite.config.ts',
            'apps/r-link-web/tsconfig.json', 'apps/r-link-web/tsconfig.node.json',
            'apps/r-link-web/src/main.tsx'}
NAS_FILES = {'compose.yaml', 'Dockerfile.server', 'Dockerfile.web', 'nginx.conf',
             'requirements.lock', '.env.example', 'init.sh', 'rlink.sh', 'README.md',
             'compose.rfile-files.yaml', 'compose.tools.yaml'}


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args])


def allowed(name):
    path = PurePosixPath(name)
    if any(part in {'build', 'dist', 'target', 'node_modules', '__pycache__', 'data', 'logs', 'config'} for part in path.parts):
        return False
    if name in REQUIRED or name in {'.dockerignore', 'scripts/build_nas_package.py', 'docs/desktop-nas-rfile-20261003.md'}:
        return True
    if path.parent.as_posix() == 'deploy/nas':
        return path.name in NAS_FILES
    if name.startswith(('R-Link-Server/api/', 'R-Link-Server/core/', 'R-Link-Server/builtin/')):
        return path.suffix in {'.py', '.yaml'}
    if name.startswith('apps/r-link-web/src/'):
        return path.suffix in {'.tsx', '.ts', '.css', '.svg', '.json', '.png'} and '.test.' not in path.name
    return False


def digest_file(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def inspect_images(path, version, commit):
    """Read docker-save configs without executing images or trusting user metadata."""
    result = []
    expected = {f'rlink-nas-{role}:{version}' for role in ('server', 'web')}
    with tarfile.open(path, 'r:*') as archive:
        records = json.load(archive.extractfile('manifest.json'))
        for record in records:
            tags = record.get('RepoTags') or []
            if len(tags) != 1 or tags[0] not in expected:
                raise ValueError('Offline archive must contain only the two versioned R-Link image tags')
            data = archive.extractfile(record['Config']).read()
            image = json.loads(data)
            if image.get('os') != 'linux' or image.get('architecture') != 'amd64':
                raise ValueError('DS918+ offline images must be linux/amd64')
            config = image.get('config') or {}
            if tags[0].startswith('rlink-nas-server:') and config.get('User') != '10001':
                raise ValueError('Server image must use non-root UID 10001')
            for entry in config.get('Env') or []:
                key, _, value = entry.partition('=')
                if value and (any(term in key.upper() for term in ('TOKEN', 'SECRET', 'PASSWORD', 'PROXY'))):
                    raise ValueError('Image config contains a secret or build proxy')
            if (config.get('Labels') or {}).get('org.opencontainers.image.revision') != commit:
                raise ValueError('Offline image source commit does not match the packaged source commit')
            result.append({'tag': tags[0], 'id': 'sha256:' + hashlib.sha256(data).hexdigest(), 'platform': 'linux/amd64'})
    if {image['tag'] for image in result} != expected or len(result) != 2:
        raise ValueError('Offline archive is missing a server or web image')
    return sorted(result, key=lambda image: image['tag'])


def build_package(root, ref, output, version, image_archive=None):
    root, output = Path(root), Path(output)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,79}', version):
        raise ValueError('Invalid release version')
    commit = git(root, 'rev-parse', '--verify', ref + '^{commit}').decode().strip()
    epoch = int(git(root, 'show', '-s', '--format=%ct', commit))
    files = {}
    for entry in git(root, 'ls-tree', '-r', '-z', commit).split(b'\0'):
        if not entry:
            continue
        metadata, name_bytes = entry.split(b'\t', 1)
        name = name_bytes.decode('utf-8')
        mode, kind, object_id = metadata.decode().split()
        if allowed(name):
            if kind != 'blob' or mode not in {'100644', '100755'}:
                raise ValueError('Package source must be regular Git blobs: ' + name)
            data = git(root, 'cat-file', 'blob', object_id)
            if name.endswith('.sh'):
                data = data.replace(b'\r\n', b'\n')
            files[name] = data
    missing = REQUIRED - files.keys()
    if missing:
        raise ValueError('Missing required package source: ' + ', '.join(sorted(missing)))
    files['deploy/nas/.env.example'] = files['deploy/nas/.env.example'].replace(b'R_LINK_SOURCE_COMMIT=source-checkout', b'R_LINK_SOURCE_COMMIT=' + commit.encode())
    files['deploy/nas/.env.example'] = re.sub(rb'^R_LINK_IMAGE_TAG=.*$', b'R_LINK_IMAGE_TAG=' + version.encode(), files['deploy/nas/.env.example'], flags=re.MULTILINE)
    images = inspect_images(Path(image_archive), version, commit) if image_archive else []
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    if image_archive:
        hashes['images.tar'] = digest_file(Path(image_archive))
    manifest = {'format': 1, 'version': version, 'source_commit': commit, 'source_epoch': epoch,
                'target': {'model': 'DS918+', 'dsm': '7.1.1', 'arch': 'apollolake', 'cpu': 'x86_64'},
                'installer': 'Docker Compose (not a Package Center SPK)',
                'source_build_platforms': ['linux/amd64', 'linux/arm64'],
                'built_platforms': ['linux/amd64'] if images else [], 'images': images, 'files': hashes}
    manifest_bytes = (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode()
    files['PACKAGE-MANIFEST.json'] = manifest_bytes
    suffix = 'DS918plus-DSM7.1.1-apollolake-amd64-offline' if images else 'source-amd64-arm64'
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f'r-link-nas-{version}-{suffix}.tar.gz'
    temporary = destination.with_suffix('.tmp')
    try:
        with temporary.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=epoch) as compressed:
            with tarfile.open(fileobj=compressed, mode='w|', format=tarfile.PAX_FORMAT) as archive:
                for name in sorted(files.keys() | ({'images.tar'} if image_archive else set())):
                    info = tarfile.TarInfo('r-link-nas/' + name)
                    info.mtime = epoch
                    info.mode = 0o755 if name.endswith('.sh') else 0o644
                    info.size = Path(image_archive).stat().st_size if name == 'images.tar' else len(files[name])
                    if name == 'images.tar':
                        with Path(image_archive).open('rb') as source:
                            archive.addfile(info, source)
                    else:
                        archive.addfile(info, io.BytesIO(files[name]))
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    destination.with_suffix(destination.suffix + '.sha256').write_text(digest_file(destination) + '  ' + destination.name + '\n', encoding='utf-8')
    destination.with_suffix('.manifest.json').write_bytes(manifest_bytes)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--version', default='0.1.0-nas.20261003')
    parser.add_argument('--image-archive', type=Path)
    args = parser.parse_args()
    print(build_package(args.root, args.ref, args.output, args.version, args.image_archive))


if __name__ == '__main__':
    main()
