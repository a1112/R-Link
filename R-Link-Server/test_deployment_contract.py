"""Docker builds must have every host COPY input in a fresh checkout."""
from pathlib import Path
import shlex

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('dockerfile,context', [
    (ROOT / 'deploy' / 'Dockerfile.web', ROOT),
    (ROOT / 'R-Link-Server' / 'Dockerfile', ROOT / 'R-Link-Server'),
])
def test_docker_copy_inputs_exist(dockerfile, context):
    for line in dockerfile.read_text(encoding='utf-8').splitlines():
        fields = shlex.split(line)
        if not fields or fields[0].upper() != 'COPY' or any(field.startswith('--from=') for field in fields):
            continue
        sources = [field for field in fields[1:-1] if not field.startswith('--')]
        for source in sources:
            exists = context.is_dir() if source == '.' else bool(list(context.glob(source)))
            assert exists, f'{dockerfile.name}: missing COPY source {source}'
