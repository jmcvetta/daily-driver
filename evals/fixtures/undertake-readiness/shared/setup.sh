#!/usr/bin/env bash
# Build an isolated undertake-readiness scenario in the current directory.
# Run it from the sandbox root with the fixture mounted at `.fixture`:
#   bash .fixture/setup.sh <scenario>
# It makes a temporary git repository with a local bare remote, a stateful
# offline `gh` at `.fixture/bin/gh`, and a harmless maintenance script. No
# network, no credential, no real repository.
set -euo pipefail
scenario="${1:?scenario required}"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "${here}/published"
chmod +x "${here}/bin/gh" "${here}/verify.py"
: >"${here}/ops.log"
: >"${here}/service.log"
printf '%s\n' "${scenario}" >"${here}/scenario"

git init -q -b master .
git config user.email fixture@example.invalid
git config user.name Fixture
printf '.fixture/\n' >>.git/info/exclude
printf 'uploader\n' >uploader.txt
git add uploader.txt
git commit -qm 'base'
git init -q --bare "${here}/remote.git"
git remote add origin "${here}/remote.git"
git switch -qc issue-24-uploader-retry
printf 'retry\n' >>uploader.txt
git commit -qam 'feat: retry the upload'
review_head="$(git rev-parse HEAD)"
git switch -q master
printf 'docs\n' >README.md
git add README.md
git commit -qm 'docs: readme'
git switch -q issue-24-uploader-retry
case "${scenario}" in
  missing-notice | covered-ancestor | ci-wrong-head)
    git merge -q --no-ff master -m 'Merge master into issue-24-uploader-retry'
    ;;
  stale-notice-content)
    printf 'more\n' >>uploader.txt
    git commit -qam 'fix: handle a zero-length body'
    ;;
esac
head="$(git rev-parse HEAD)"
git push -q -u origin master issue-24-uploader-retry
git switch -q issue-24-uploader-retry

python3 "${here}/build-state.py" "${scenario}" "${review_head}" "${head}" "${here}/state.json"

if [[ "${scenario}" == service-* ]]; then
  mkdir -p scripts
  cp "${here}/pr-keep-current.sh" scripts/pr-keep-current.sh
  chmod +x scripts/pr-keep-current.sh
fi
