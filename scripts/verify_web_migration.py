"""Verify preserved Web source snapshots against tracked Git blobs."""
import json
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
records = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--stage', '-z'])
tracked = {}
for record in records.split(b'\0'):
    if record:
        header, path = record.split(b'\t', 1)
        mode, blob, stage = header.decode().split()
        assert stage == '0'
        tracked[path.decode()] = blob
directory = root / 'docs/repository-consolidation/R-Link-Web'
manifest = json.loads((directory / 'manifest.json').read_bytes())
for entry in manifest['files']:
    assert tracked[entry['target_path']] == entry['target_git_blob'], entry['target_path']
    if entry.get('archive_path'):
        assert tracked[entry['archive_path']] == entry['source_git_blob'], entry['archive_path']
    if entry.get('local_path'):
        assert entry['local_path'] not in tracked
review = json.loads((directory / 'dependency-branch-review.json').read_bytes())
assert tracked[review['archive_path']] == review['archive_git_blob']
print(f"Verified {len(manifest['files'])} main source paths and dependency branch original")
