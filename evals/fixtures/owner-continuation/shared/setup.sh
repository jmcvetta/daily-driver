#!/usr/bin/env bash
set -euo pipefail
scenario="${1:?scenario required}"
bash .fixture/setup.sh service-ok
git merge -q --no-ff master -m 'Merge master'
git push -q origin HEAD
python3 .continuation/initialize.py "$scenario"
chmod +x .continuation/bin/gh
printf '%s\n' "$scenario" > .continuation/scenario
printf '0\n' > .continuation/windows
: > .continuation/operations.jsonl
