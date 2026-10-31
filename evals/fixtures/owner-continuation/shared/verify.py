#!/usr/bin/env python3
"""Check the recorded offline CI observations for one continuation."""
import json
import re
import sys
from pathlib import Path

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
