#!/usr/bin/env bash
set -euo pipefail
bash .fixture/setup.sh service-exits-early
git switch -q master
printf 'uploader\nbase setting\n' > uploader.txt
git commit -qam 'Change uploader configuration on master'
git switch -q issue-24-uploader-retry
git checkout -q master -- README.md
git commit -qm 'Track README on feature branch'
printf 'uploader\nretry setting\n' > uploader.txt
git commit -qam 'Change uploader configuration on feature branch'
printf 'unrelated unstaged change\n' >> README.md
test "$(git status --porcelain -- README.md)" = ' M README.md'
test -z "$(git diff --cached -- README.md)"
git push -q origin master issue-24-uploader-retry
python3 .continuation/initialize.py conflict
printf 'start pr=25 pid=100\nmerge conflict in uploader.txt\nexit status=3\n' > .fixture/service.log
