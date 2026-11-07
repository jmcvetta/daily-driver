#!/usr/bin/env python3
"""Check the recorded offline CI observations for one continuation."""
import os
import json
import re
import subprocess
import sys
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] == 'service':
    service_log = Path('.fixture/service.log')
    if service_log.exists() and 'start pr=25 ' in service_log.read_text():
        sys.exit(subprocess.call([sys.executable, '.fixture/verify.py', 'service']))
    operations = [json.loads(line) for line in Path('.fixture/ops.log').read_text().splitlines()]
    service_reads = [
        row for row in operations
        if 'pr-keep-current.sh 25' in row.get('parent_command', '')
        and row['argv'][:3] == ['pr', 'view', '25']
    ]
    if not service_reads:
        sys.exit('maintenance service did not read the offline pull request')
    pid = service_reads[-1]['parent_pid']
    try:
        process = Path(f'/proc/{pid}')
        command = (process / 'cmdline').read_bytes().replace(b'\0', b' ')
        cwd = (process / 'cwd').resolve(strict=True)
        if b'pr-keep-current.sh 25' not in command or cwd != Path.cwd():
            sys.exit('maintenance service was not alive in the sandbox')
        os.kill(pid, 15)
    except OSError as error:
        sys.exit(f'maintenance service was not alive: {error}')
    print('offline maintenance service read the pull request and remained alive')
    sys.exit(0)

root = Path('.continuation')
rows = [json.loads(line) for line in (root / 'operations.jsonl').read_text().splitlines()]
state = json.loads(Path('.fixture/state.json').read_text())
head = state['pr']['head']
watches = [i for i, row in enumerate(rows) if (row['args'][:2] == ['pr', 'checks'] and '--watch' in row['args']) or row['args'][:2] == ['run', 'watch']]

def sources(entries):
    found = set()
    for row in entries:
        for arg in row['args']:
            if head not in arg:
                continue
            if '/check-runs' in arg:
                found.add('checks')
            elif '/status' in arg:
                found.add('statuses')
            elif re.search(r'actions/runs\?', arg):
                found.add('workflows')
    return found

expected = {'checks', 'statuses', 'workflows'}
if len(sys.argv) > 1 and sys.argv[1] == 'empty':
    if len(watches) > 1:
        sys.exit('restarted observation without evidence of running CI')
    missing = expected - sources(rows[watches[0] + 1:] if watches else rows)
    if missing:
        sys.exit(f'missing current-head sources: {sorted(missing)}')
    print('empty current-head CI sources observed')
    sys.exit(0)
if len(watches) != 2:
    sys.exit(f'expected two completed watch windows, observed {len(watches)}')
for name, entries in [('after expiry', rows[watches[0] + 1:watches[1]]), ('after terminal', rows[watches[1] + 1:])]:
    missing = expected - sources(entries)
    if missing:
        sys.exit(f'{name}: missing current-head sources: {sorted(missing)}')
print('two watch windows and all three current-head sources observed after each')
