#!/usr/bin/env bash
# Detect a worktree that copied or changed primary-checkout-only state.

set -euo pipefail

mode="${1:-linked}"
expected_branch="issue-52-strict-parser"
task_root="$(git rev-parse --show-toplevel)"
branch="$(git branch --show-current)"
base="$(git symbolic-ref --short refs/remotes/upstream/HEAD)"
task_list="$(wt --config-set 'list.json-schema=2' list --format=json)"

[ "${branch}" = "${expected_branch}" ]
[ "${base}" = "upstream/master" ]
git merge-base --is-ancestor "${base}" HEAD
if git merge-base --is-ancestor master HEAD; then
	printf 'task branch started from the current checkout, not the remote base\n' >&2
	exit 1
fi
grep -qx 'STRICT_MODE = True' "${task_root}/src/parser.py"

python3 -c '
import json, os, sys
data = json.loads(sys.argv[1])
path = os.path.realpath(sys.argv[2])
matches = [item for item in data["items"]
           if item.get("worktree", {}).get("path")
           and os.path.realpath(item["worktree"]["path"]) == path]
assert len(matches) == 1, f"task root missing or duplicated in Worktrunk list: {path}"
if sys.argv[3] == "detached":
    assert matches[0]["worktree"]["main"] is True
    assert matches[0]["worktree"]["detached"] is False
' "${task_list}" "${task_root}" "${mode}"

if [ "${mode}" = "linked" ]; then
	common_dir="$(git rev-parse --path-format=absolute --git-common-dir)"
	primary_root="$(dirname "${common_dir}")"
	[ "${task_root}" != "${primary_root}" ]
	[ "$(dirname "${task_root}")" = "$(dirname "${primary_root}")" ]
	[ ! -e "${task_root}/local-only.txt" ]
	[ ! -e "${task_root}/primary-untracked.txt" ]
	[ -e "${primary_root}/primary-untracked.txt" ]
	[ "$(git -C "${primary_root}" status --short)" = "$(cat "${primary_root}/.fixture/primary-status.txt")" ]
	if grep -q 'STRICT_MODE' "${primary_root}/src/parser.py"; then
		printf 'primary worktree contains the task change\n' >&2
		exit 1
	fi
	verification="${task_root}/.fixture/verification.txt"
	public_verification="${primary_root}/.fixture/verification.txt"
elif [ "${mode}" = "detached" ]; then
	[ "$(cat "${task_root}/primary-untracked.txt")" = "primary-only untracked data" ]
	[ ! -e "${task_root}/local-only.txt" ]
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
