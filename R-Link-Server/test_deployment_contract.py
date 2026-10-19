"""Docker builds must have every host COPY input in a fresh checkout."""
from pathlib import Path
import shlex

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('dockerfile,context', [
    (ROOT / 'deploy' / 'Dockerfile.web', ROOT),
    (ROOT / 'R-Link-Server' / 'Dockerfile', ROOT),
    (ROOT / 'deploy' / 'nas' / 'Dockerfile.server', ROOT),
])
def test_docker_copy_inputs_exist(dockerfile, context):
    for line in dockerfile.read_text(encoding='utf-8').splitlines():
        if not line.lstrip().upper().startswith('COPY '):
            continue
        fields = shlex.split(line)
        if not fields or fields[0].upper() != 'COPY' or any(field.startswith('--from=') for field in fields):
            continue
        sources = [field for field in fields[1:-1] if not field.startswith('--')]
        for source in sources:
            exists = context.is_dir() if source == '.' else bool(list(context.glob(source)))
            assert exists, f'{dockerfile.name}: missing COPY source {source}'


def test_server_build_context_contains_the_shared_contract_and_excludes_private_state():
    compose_dir = ROOT / 'deploy'
    server = yaml.safe_load((compose_dir / 'compose.yaml').read_text(encoding='utf-8'))['services']['server']
    context = (compose_dir / server['build']['context']).resolve()
    assert context == ROOT
    assert (context / 'contracts' / 'bridgeproxy-v1.json').is_file()
    ignored = set((context / '.dockerignore').read_text(encoding='utf-8').splitlines())
    assert {'.repository-consolidation-local', '.venv', 'logs', 'R-Link-Server/config',
            'R-Link-Server/data', 'R-Link-Server/plugins', '**/.env', 'R-Link-Server/**/*.exe'} <= ignored


def test_generic_server_image_copies_only_runtime_sources():
    sources = []
    for line in (ROOT / 'R-Link-Server' / 'Dockerfile').read_text(encoding='utf-8').splitlines():
        if line.startswith('COPY '):
            sources.extend(shlex.split(line)[1:-1])
    assert set(sources) == {
        'R-Link-Server/requirements.txt', 'R-Link-Server/main.py', 'R-Link-Server/api',
        'R-Link-Server/core', 'R-Link-Server/builtin', 'R-Link-Server/interop_bridge',
        'contracts/bridgeproxy-v1.json',
    }
