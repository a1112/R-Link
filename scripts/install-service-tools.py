"""Install pinned upstream binaries after checking GitHub's SHA-256 release digest.

Usage: python scripts/install-service-tools.py [--platform windows_amd64|linux_amd64]
No programs are run, no system PATH/service settings are changed.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import platform
import tarfile
import urllib.request
import zipfile

RELEASES = [('fatedier/frp', 'v0.71.0', ('frpc', 'frps')), ('caddyserver/caddy', 'v2.11.4', ('caddy',))]


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'R-Link-service-tools'})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read(150 * 1024 * 1024)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    default = ('windows' if platform.system() == 'Windows' else 'linux') + '_' + ('arm64' if platform.machine().lower() in ('aarch64', 'arm64') else 'amd64')
    parser.add_argument('--platform', default=default, choices=['windows_amd64', 'windows_arm64', 'linux_amd64', 'linux_arm64'])
    parser.add_argument('--dest', type=Path, default=Path(__file__).resolve().parents[1] / 'binaries')
    args = parser.parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    windows = args.platform.startswith('windows')
    suffix = '.zip' if windows else '.tar.gz'
    for repository, version, programs in RELEASES:
        metadata = json.loads(fetch(f'https://api.github.com/repos/{repository}/releases/tags/{version}'))
        asset = next(item for item in metadata['assets'] if item['name'].endswith(args.platform + suffix))
        expected = asset.get('digest', '')
        if not expected.startswith('sha256:'):
            raise RuntimeError('Upstream did not publish a SHA-256 digest; refusing installation')
        archive = fetch(asset['browser_download_url'])
        if 'sha256:' + hashlib.sha256(archive).hexdigest() != expected:
            raise RuntimeError('Release digest mismatch')
        names = {name + ('.exe' if windows else '') for name in programs}
        if windows:
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                files = [(PurePosixPath(item.filename).name, package.read(item)) for item in package.infolist()
                         if PurePosixPath(item.filename).name in names and not item.is_dir()]
        else:
            with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as package:
                files = [(PurePosixPath(item.name).name, package.extractfile(item).read()) for item in package.getmembers()
                         if PurePosixPath(item.name).name in names and item.isfile()]
        if len(files) != len(names) or {name for name, _ in files} != names:
            raise RuntimeError('Release does not contain the expected binaries')
        for name, contents in files:
            target = args.dest / name
            if target.exists():
                if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(contents).digest():
                    raise RuntimeError(f'{target} already exists with different content; move it before installing')
            else:
                with target.open('xb') as output:
                    output.write(contents)
                target.chmod(0o755)
            print(f'Verified {repository} {version}: {target}')


if __name__ == '__main__':
    main()
