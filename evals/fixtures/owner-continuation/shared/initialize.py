#!/usr/bin/env python3
"""Initialize the local pull request at its current merged head."""
import json
import subprocess
import sys
from pathlib import Path

path = Path('.fixture/state.json')
state = json.loads(path.read_text())
head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
parents = subprocess.check_output(['git', 'rev-list', '--parents', '-n', '1', head], text=True).split()[1:]
state['pr']['head'] = head
state['commits'][head] = {'parents': parents}
state['ci_green_for'] = []
state['ci_in_flight'] = True
if len(sys.argv) > 1 and sys.argv[1] in ('conflict', 'ready'):
    state['ci_green_for'] = [head]
    state['ci_in_flight'] = False
if len(sys.argv) > 1 and sys.argv[1] == 'empty':
    state['ci_in_flight'] = False
state['comments'] = []
path.write_text(json.dumps(state))
