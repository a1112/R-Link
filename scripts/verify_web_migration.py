"""Verify immutable source preservation without freezing maintained application code."""
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
def verify_entries(entries):
    for entry in entries:
        target = entry['target_path']
        assert target in tracked and (root / target).is_file(), target
        preserved = entry.get('archive_path', target)
        expected = entry.get('source_git_blob')
        if entry.get('disposition') == 'redacted_local_configuration':
            expected = entry['target_git_blob']
        assert tracked[preserved] == expected, preserved
        # Detect unstaged edits too, using Git's line-ending normalization.
        actual = subprocess.check_output(['git', '-C', str(root), 'hash-object', '--path=' + preserved, preserved]).decode().strip()
        assert actual == expected, preserved
        if entry.get('local_path'):
            assert entry['local_path'] not in tracked

verify_entries(manifest['files'])
followup = json.loads((directory / 'source-head-review.json').read_bytes())
verify_entries(followup['files'])
review = json.loads((directory / 'dependency-branch-review.json').read_bytes())
assert tracked[review['archive_path']] == review['archive_git_blob']
print(f"Verified {len(manifest['files'])} baseline source paths, {len(followup['files'])} follow-up paths and dependency branch original")
