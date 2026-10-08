#!/usr/bin/env bash
# Detect a worktree that copied or changed primary-checkout-only state.

set -euo pipefail

mode="${1:-linked}"
expected_branch="issue-52-strict-parser"
primary_branch="master"
if [ "${mode}" = "designated" ]; then
	expected_branch="issue-52-designated-route"
	primary_branch="claude/designated-52"
fi
task_root="$(git rev-parse --show-toplevel)"
branch="$(git branch --show-current)"
remote_branch="${branch}"
base="$(git symbolic-ref --short refs/remotes/upstream/HEAD)"
task_list="$(wt --config-set 'list.json-schema=2' list --format=json)"

[ "${branch}" = "${expected_branch}" ]
[ "${base}" = "upstream/master" ]
if git merge-base --is-ancestor "refs/heads/${primary_branch}" HEAD; then
	printf 'task branch started from the primary branch, not the remote base\n' >&2
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

if [ "${mode}" = "resume" ]; then
	remote_tip="$(git ls-remote upstream refs/heads/issue-52-strict-parser | cut -f1)"
	[ -n "${remote_tip}" ]
	git merge-base --is-ancestor "${remote_tip}" HEAD
	[ -e "${task_root}/src/resumed.txt" ]
fi

if [ "${mode}" = "linked" ] || [ "${mode}" = "resume" ] || [ "${mode}" = "designated" ]; then
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
	# Catch pushing the local-only name or moving the primary designation ref.
	if [ "${mode}" = "designated" ]; then
		designated="claude/designated-52"
		[ "$(git -C "${primary_root}" branch --show-current)" = "${designated}" ]
		[ "$(git -C "${primary_root}" rev-parse HEAD)" = "$(cat "${primary_root}/.fixture/primary-tip.txt")" ]
		[ "$(git -C "${primary_root}" rev-parse "refs/heads/${designated}")" = "$(cat "${primary_root}/.fixture/primary-tip.txt")" ]
		[ "$(git -C "${task_root}" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}')" = "upstream/${designated}" ]
		remote_branch="${designated}"
		remote_task="$(git -C "${task_root}" ls-remote upstream "refs/heads/${designated}" | cut -f1)"
		[ -n "${remote_task}" ]
		[ "${remote_task}" = "$(git -C "${task_root}" rev-parse HEAD)" ]
		[ -z "$(git -C "${task_root}" ls-remote upstream refs/heads/issue-52-designated-route)" ]
		[ "$(git -C "${primary_root}" branch --show-current)" = "$(cat "${primary_root}/.fixture/primary-branch.txt")" ]
	fi
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
if [ "${mode}" = "designated" ]; then
	cat >"${task_root}/.fixture/designated-outcome.txt" <<EOF
execution-branch=${branch}
remote-branch=${remote_branch}
base=${base}
remote-head=${remote_task}
primary-branch=$(git -C "${primary_root}" branch --show-current)
primary-tip=$(git -C "${primary_root}" rev-parse HEAD)
primary-status=unchanged
remote-execution-branch=absent
EOF
fi

if [ "${public_verification}" != "${verification}" ]; then
	ln -sfn "${verification}" "${public_verification}"
fi
