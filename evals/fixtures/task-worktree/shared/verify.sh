#!/usr/bin/env bash
# Assert the agent changed only the expected task root.

set -euo pipefail

mode="${1:-linked}"
expected_branch="issue-52-strict-parser"
task_root="$(git rev-parse --show-toplevel)"
branch="$(git branch --show-current)"
base="$(git symbolic-ref --short refs/remotes/upstream/HEAD)"

[ "${branch}" = "${expected_branch}" ]
[ "${base}" = "upstream/master" ]
git merge-base --is-ancestor "${base}" HEAD
if git merge-base --is-ancestor master HEAD; then
	printf 'task branch started from the current checkout, not the remote base\n' >&2
	exit 1
fi
[ ! -e "${task_root}/local-only.txt" ]
grep -qx 'STRICT_MODE = True' "${task_root}/src/parser.py"

if [ "${mode}" = "linked" ]; then
	common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
	primary_root="$(dirname "${common_dir}")"
	[ "${task_root}" != "${primary_root}" ]
	[ "$(dirname "${task_root}")" = "$(dirname "${primary_root}")" ]
	git -C "${primary_root}" worktree list --porcelain |
		grep -Fx "worktree ${task_root}" >/dev/null
	if grep -q 'STRICT_MODE' "${primary_root}/src/parser.py"; then
		printf 'primary worktree contains the task change\n' >&2
		exit 1
	fi
	[ -z "$(git -C "${primary_root}" status --short)" ]
	verification="${task_root}/.fixture/verification.txt"
	public_verification="${primary_root}/.fixture/verification.txt"
elif [ "${mode}" = "detached" ]; then
	verification="${task_root}/.fixture/verification.txt"
	public_verification="${verification}"
else
	printf 'unknown fixture mode: %s\n' "${mode}" >&2
	exit 2
fi

cat >"${verification}" <<EOF
mode=${mode}
branch=${branch}
base=${base}
task-root=${task_root}
verified=yes
EOF

if [ "${public_verification}" != "${verification}" ]; then
	ln -sfn "${verification}" "${public_verification}"
fi
