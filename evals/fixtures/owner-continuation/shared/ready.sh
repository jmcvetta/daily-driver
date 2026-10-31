#!/usr/bin/env bash
set -euo pipefail
bash .fixture/setup.sh service-ok
git merge -q --no-ff master -m 'Merge master'
git push -q origin HEAD
python3 .continuation/initialize.py ready
