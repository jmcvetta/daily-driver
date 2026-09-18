#!/usr/bin/env bash
# Exercise both repository shapes used by the task-worktree behavior evals.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="${REPO_ROOT}/evals/fixtures/task-worktree/shared"
ROOT="$(mktemp -d)"
trap 'rm -rf "${ROOT}"' EXIT

copy_fixture() {
	local primary="$1"
	mkdir -p "${primary}/.fixture"
	cp -R "${FIXTURE}/." "${primary}/.fixture/"
}

PRIMARY="${ROOT}/linked-primary"
TASK_ROOT="${ROOT}/task-worktree-issue-52"
copy_fixture "${PRIMARY}"
(
	cd "${PRIMARY}"
	bash .fixture/setup.sh linked
	git worktree add -b issue-52-strict-parser "${TASK_ROOT}" upstream/master >/dev/null
)
printf '\nSTRICT_MODE = True\n' >>"${TASK_ROOT}/src/parser.py"
(
	cd "${TASK_ROOT}"
	bash .fixture/verify.sh linked
)
grep -qx 'verified=yes' "${PRIMARY}/.fixture/verification.txt"
[ -L "${PRIMARY}/.fixture/verification.txt" ]
git -C "${PRIMARY}" worktree remove --force "${TASK_ROOT}"
[ ! -e "${PRIMARY}/.fixture/verification.txt" ]

DETACHED="${ROOT}/detached-task"
copy_fixture "${DETACHED}"
(
	cd "${DETACHED}"
	bash .fixture/setup.sh detached
	git switch -c issue-52-strict-parser upstream/master >/dev/null
	printf '\nSTRICT_MODE = True\n' >>src/parser.py
	bash .fixture/verify.sh detached
)
grep -qx 'verified=yes' "${DETACHED}/.fixture/verification.txt"

printf 'task-worktree fixtures establish and verify linked and detached task roots\n'
