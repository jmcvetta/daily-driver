#!/usr/bin/env bash
# Catch use of primary-only state, pushing the local name, or clobbering an unrelated designated head.

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


# A recorded task branch that only exists on its remote must resume at that tip.
RESUME_PRIMARY="${ROOT}/resume primary"
copy_fixture "${RESUME_PRIMARY}"
(
	cd "${RESUME_PRIMARY}"
	bash .fixture/setup.sh resume
)
RESUME_BASELINE="$(git -C "${RESUME_PRIMARY}" status --short)"
git -C "${RESUME_PRIMARY}" fetch upstream \
	"+refs/heads/${TASK_BRANCH}:refs/remotes/upstream/${TASK_BRANCH}" >/dev/null
RESUME_TIP="$(git -C "${RESUME_PRIMARY}" rev-parse "upstream/${TASK_BRANCH}")"
resumed="$(wt -C "${RESUME_PRIMARY}" switch --create "${TASK_BRANCH}" \
	--base "upstream/${TASK_BRANCH}" --no-cd --format=json)"
RESUME_ROOT="$(json_path "${resumed}")"
[ "$(git -C "${RESUME_ROOT}" branch --show-current)" = "${TASK_BRANCH}" ]
[ "$(git -C "${RESUME_ROOT}" rev-parse HEAD)" = "${RESUME_TIP}" ]
[ -e "${RESUME_ROOT}/src/resumed.txt" ]
printf '\nSTRICT_MODE = True\n' >>"${RESUME_ROOT}/src/parser.py"
(
	cd "${RESUME_ROOT}"
	bash .fixture/verify.sh resume
)
[ "$(git -C "${RESUME_PRIMARY}" status --short)" = "${RESUME_BASELINE}" ]

# A primary-held designation gets a sibling execution branch based at remote
# master, then pushes only that commit to the different designated remote name.
DESIGNATED_PRIMARY="${ROOT}/designated primary"
DESIGNATED_BRANCH="claude/designated-52"
EXECUTION_BRANCH="issue-52-designated-route"
copy_fixture "${DESIGNATED_PRIMARY}"
(
	cd "${DESIGNATED_PRIMARY}"
	bash .fixture/setup.sh designated
)
DESIGNATED_BASELINE="$(git -C "${DESIGNATED_PRIMARY}" status --short)"
DESIGNATED_PRIMARY_SHA="$(git -C "${DESIGNATED_PRIMARY}" rev-parse HEAD)"
[ "$(git -C "${DESIGNATED_PRIMARY}" branch --show-current)" = "${DESIGNATED_BRANCH}" ]
[ -z "$(git -C "${DESIGNATED_PRIMARY}" ls-remote upstream "refs/heads/${DESIGNATED_BRANCH}")" ]
created="$(wt -C "${DESIGNATED_PRIMARY}" switch --create "${EXECUTION_BRANCH}" \
	--base upstream/master --no-cd --format=json)"
DESIGNATED_ROOT="$(json_path "${created}")"
[ "$(git -C "${DESIGNATED_ROOT}" branch --show-current)" = "${EXECUTION_BRANCH}" ]
[ "$(git -C "${DESIGNATED_ROOT}" rev-parse HEAD)" = "$(git -C "${DESIGNATED_PRIMARY}" rev-parse upstream/master)" ]
[ ! -e "${DESIGNATED_ROOT}/local-only.txt" ]
[ ! -e "${DESIGNATED_ROOT}/primary-untracked.txt" ]
printf '\nSTRICT_MODE = True\n' >>"${DESIGNATED_ROOT}/src/parser.py"
git -C "${DESIGNATED_ROOT}" add src/parser.py
git -C "${DESIGNATED_ROOT}" commit -m "Apply designated branch task" >/dev/null
git -C "${DESIGNATED_ROOT}" push -u upstream \
	"${EXECUTION_BRANCH}:${DESIGNATED_BRANCH}" >/dev/null
(
	cd "${DESIGNATED_ROOT}"
	bash .fixture/verify.sh designated
)
[ "$(git -C "${DESIGNATED_PRIMARY}" branch --show-current)" = "${DESIGNATED_BRANCH}" ]
[ "$(git -C "${DESIGNATED_PRIMARY}" rev-parse HEAD)" = "${DESIGNATED_PRIMARY_SHA}" ]
[ "$(git -C "${DESIGNATED_PRIMARY}" status --short)" = "${DESIGNATED_BASELINE}" ]

# A pre-existing unrelated remote head must remain a collision; accepting a
# force push here would discard work and lie about the claimed task branch.
COLLISION_PRIMARY="${ROOT}/designated collision primary"
copy_fixture "${COLLISION_PRIMARY}"
(
	cd "${COLLISION_PRIMARY}"
	bash .fixture/setup.sh designated
)
COLLISION_BASELINE="$(git -C "${COLLISION_PRIMARY}" status --short)"
COLLISION_EXECUTION_ROOT="$(json_path "$(wt -C "${COLLISION_PRIMARY}" switch --create "${EXECUTION_BRANCH}" \
	--base upstream/master --no-cd --format=json)")"
printf '\nSTRICT_MODE = True\n' >>"${COLLISION_EXECUTION_ROOT}/src/parser.py"
git -C "${COLLISION_EXECUTION_ROOT}" add src/parser.py
git -C "${COLLISION_EXECUTION_ROOT}" commit -m "Apply collision task" >/dev/null
UNRELATED_SOURCE="${ROOT}/unrelated remote source"
git clone "${COLLISION_PRIMARY}/.fixture/upstream.git" "${UNRELATED_SOURCE}" >/dev/null
git -C "${UNRELATED_SOURCE}" config user.name "Eval Fixture"
git -C "${UNRELATED_SOURCE}" config user.email "fixture@example.invalid"
git -C "${UNRELATED_SOURCE}" switch --orphan unrelated-designation >/dev/null
printf 'unrelated remote work\n' >"${UNRELATED_SOURCE}/unrelated.txt"
git -C "${UNRELATED_SOURCE}" add unrelated.txt
git -C "${UNRELATED_SOURCE}" commit -m "Create unrelated designated head" >/dev/null
git -C "${UNRELATED_SOURCE}" push origin "HEAD:refs/heads/${DESIGNATED_BRANCH}" >/dev/null
git -C "${COLLISION_EXECUTION_ROOT}" fetch upstream \
	"+refs/heads/${DESIGNATED_BRANCH}:refs/remotes/upstream/${DESIGNATED_BRANCH}" >/dev/null
UNRELATED_TIP="$(git -C "${COLLISION_EXECUTION_ROOT}" rev-parse "upstream/${DESIGNATED_BRANCH}")"
if git -C "${COLLISION_EXECUTION_ROOT}" merge-base --is-ancestor \
	"upstream/${DESIGNATED_BRANCH}" HEAD; then
	printf 'unrelated designated head unexpectedly belongs to the task\n' >&2
	exit 1
fi
if git -C "${COLLISION_EXECUTION_ROOT}" push upstream \
	"${EXECUTION_BRANCH}:${DESIGNATED_BRANCH}" >/dev/null 2>&1; then
	printf 'non-force push replaced an unrelated designated head\n' >&2
	exit 1
fi
[ "$(git -C "${COLLISION_EXECUTION_ROOT}" ls-remote upstream \
	"refs/heads/${DESIGNATED_BRANCH}" | cut -f1)" = "${UNRELATED_TIP}" ]
[ "$(git -C "${COLLISION_PRIMARY}" branch --show-current)" = "${DESIGNATED_BRANCH}" ]
[ "$(git -C "${COLLISION_PRIMARY}" rev-parse HEAD)" = "$(cat "${COLLISION_PRIMARY}/.fixture/primary-tip.txt")" ]
[ "$(git -C "${COLLISION_PRIMARY}" status --short)" = "${COLLISION_BASELINE}" ]

printf 'Worktrunk task fixtures verify base selection, remote-task resume, designated push mapping, reuse, isolation, collisions and detached attachment\n'
