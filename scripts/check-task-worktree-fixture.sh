#!/usr/bin/env bash
# Catch task worktrees that use current HEAD, copy primary data, clobber paths or fail to reuse.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FIXTURE="${REPO_ROOT}/evals/fixtures/task-worktree/shared"
ROOT="$(mktemp -d)"
trap 'rm -rf "${ROOT}"' EXIT

if ! command -v wt >/dev/null 2>&1; then
	printf 'Worktrunk CLI required: install wt before running this fixture\n' >&2
	exit 1
fi

CONFIG="${ROOT}/worktrunk.toml"
SYSTEM_CONFIG="${ROOT}/system-worktrunk.toml"
PROJECT_CONFIG="${ROOT}/project-worktrunk.toml"
cat >"${CONFIG}" <<'EOF'
worktree-path = "{{ repo_path }}.{{ branch | sanitize }} with spaces"
skip-shell-integration-prompt = true
EOF
: >"${SYSTEM_CONFIG}"
: >"${PROJECT_CONFIG}"
export WORKTRUNK_CONFIG_PATH="${CONFIG}"
export WORKTRUNK_SYSTEM_CONFIG_PATH="${SYSTEM_CONFIG}"
export WORKTRUNK_PROJECT_CONFIG_PATH="${PROJECT_CONFIG}"
unset WORKTRUNK_WORKTREE_PATH

copy_fixture() {
	local primary="$1"
	mkdir -p "${primary}/.fixture"
	cp -R "${FIXTURE}/." "${primary}/.fixture/"
}

json_path() {
	python3 -c 'import json,sys; print(json.load(sys.stdin)["path"])' <<<"$1"
}

json_branch_path() {
	python3 -c '
import json, os, sys
branch = sys.argv[2]
data = json.loads(sys.argv[1])
items = [item for item in data["items"] if item.get("branch") == branch]
assert len(items) == 1, f"expected one Worktrunk row for {branch}, got {len(items)}"
print(items[0]["worktree"]["path"])
' "$1" "$2"
}

PRIMARY="${ROOT}/linked primary"
TASK_BRANCH="issue-52-strict-parser"
copy_fixture "${PRIMARY}"
(
	cd "${PRIMARY}"
	bash .fixture/setup.sh linked
)
BASELINE="$(git -C "${PRIMARY}" status --short)"
wt -C "${PRIMARY}" config show >/dev/null
created="$(wt -C "${PRIMARY}" switch --create "${TASK_BRANCH}" --base upstream/master --no-cd --format=json)"
TASK_ROOT="$(json_path "${created}")"
[ "${TASK_ROOT}" = "${PRIMARY}.${TASK_BRANCH} with spaces" ]
[ "$(dirname "${TASK_ROOT}")" = "$(dirname "${PRIMARY}")" ]
[ "$(git -C "${TASK_ROOT}" branch --show-current)" = "${TASK_BRANCH}" ]
[ ! -e "${TASK_ROOT}/local-only.txt" ]
[ ! -e "${TASK_ROOT}/primary-untracked.txt" ]
[ "$(git -C "${TASK_ROOT}" rev-parse HEAD)" = "$(git -C "${PRIMARY}" rev-parse upstream/master)" ]

printf '\nSTRICT_MODE = True\n' >>"${TASK_ROOT}/src/parser.py"
(
	cd "${TASK_ROOT}"
	bash .fixture/verify.sh linked
)
grep -qx 'verified=yes' "${PRIMARY}/.fixture/verification.txt"
[ -L "${PRIMARY}/.fixture/verification.txt" ]

# Selecting the existing task branch must return the registered same-task path.
reused="$(wt -C "${PRIMARY}" switch "${TASK_BRANCH}" --no-cd --format=json)"
[ "$(json_path "${reused}")" = "${TASK_ROOT}" ]
[ "$(json_branch_path "$(wt -C "${PRIMARY}" --config-set 'list.json-schema=2' list --format=json)" "${TASK_BRANCH}")" = "${TASK_ROOT}" ]

# An occupied custom-template path is a collision, not permission to clobber it.
COLLISION_BRANCH="issue-52-collision"
COLLISION_PATH="${PRIMARY}.${COLLISION_BRANCH} with spaces"
mkdir -p "${COLLISION_PATH}"
printf 'keep this path\n' >"${COLLISION_PATH}/sentinel"
if wt -C "${PRIMARY}" switch --create "${COLLISION_BRANCH}" --base upstream/master --no-cd --format=json >/dev/null 2>&1; then
	printf 'Worktrunk accepted an occupied worktree path\n' >&2
	exit 1
fi
[ "$(cat "${COLLISION_PATH}/sentinel")" = "keep this path" ]
[ "$(git -C "${PRIMARY}" status --short)" = "${BASELINE}" ]
[ "$(cat "${PRIMARY}/primary-untracked.txt")" = "primary-only untracked data" ]

# A detached task root is attached in place; it does not create a second tree.
DETACHED="${ROOT}/detached task"
copy_fixture "${DETACHED}"
(
	cd "${DETACHED}"
	bash .fixture/setup.sh detached
	git switch -c "${TASK_BRANCH}" upstream/master >/dev/null
	printf '\nSTRICT_MODE = True\n' >>src/parser.py
	bash .fixture/verify.sh detached
)
[ "$(git -C "${DETACHED}" branch --show-current)" = "${TASK_BRANCH}" ]
[ "$(json_branch_path "$(wt -C "${DETACHED}" --config-set 'list.json-schema=2' list --format=json)" "${TASK_BRANCH}")" = "${DETACHED}" ]

printf 'Worktrunk task fixtures verify base selection, reuse, isolation, collisions and detached attachment\n'
