#!/usr/bin/env bash
set -euo pipefail
bash .fixture/setup.sh service-exits-early
git switch -q master
printf 'base uploader configuration\n' > uploader.txt
git commit -qam 'Change uploader configuration on master'
git switch -q issue-24-uploader-retry
printf 'feature uploader configuration\n' > uploader.txt
git commit -qam 'Change uploader configuration on feature branch'
git push -q origin master issue-24-uploader-retry
python3 .continuation/initialize.py conflict
printf 'start pr=25 pid=100\nmerge conflict in uploader.txt\nexit status=3\n' > .fixture/service.log
