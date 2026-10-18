#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
if os.environ.get('GITHUB_EVENT_NAME') == 'pull_request':
    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())
    assert event['pull_request']['head']['ref'] == 'staging', 'Main accepts staging only'
    assert event['pull_request']['head']['repo']['full_name'] == event['repository']['full_name'], 'Promotion must use this repository staging'
files = subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines()
assert not any(x.startswith(('data/', 'backups/', 'local-handover/')) or x == 'deploy/.env' or x.startswith('.cutover.') for x in files)
for line in (root/'compose.yaml').read_text().splitlines():
    if line.strip().startswith('image:'):
        assert '@sha256:' in line, 'Pin every runtime image'
assert 'contents: read' in (root/'.github/workflows/quality.yml').read_text()
print('PASS source and promotion policy')
