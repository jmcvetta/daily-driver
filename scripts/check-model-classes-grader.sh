#!/usr/bin/env bash
#
# The acceptance test for the model-classes grader,
# `evals/fixtures/model-classes/shared/apply-tests.sh`. Needs git and bash; no
# model, no credentials, no network, so it runs in CI while the cases it grades
# do not.
#
# The failure it guards against is silent. A grader whose `tests.patch` does
# not apply scores the case 0, and a 0 reads exactly like a model that could
# not do the work. The first Claude Code smoke run of the suite scored three
# correct changes 0 that way: each added a test in the file the answer key
# rewrites. Each case below builds a throwaway repository, leaves the tree the
# way an agent might, runs the grader, and asserts the answer key landed.
#
#   same-hunk      the agent edited the lines the patch rewrites, and an
#                  implementation file the patch never names
#   new-file       the patch adds a test file the agent also created
#   committed      the agent committed its work, so HEAD is not the base
#   clean          the agent touched no test file at all
#
# Usage: scripts/check-model-classes-grader.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRADER="${REPO_ROOT}/evals/fixtures/model-classes/shared/apply-tests.sh"

fail() {
	echo "check-model-classes-grader: $*" >&2
	exit 1
}

# Build a repository at its base commit, derive `tests.patch` from a merge
# state, and leave the working tree at the base with `.fixture/` in place.
setup() {
	local dir="$1"
	git init -q "${dir}"
	cd "${dir}"
	git config user.email "check@example.invalid"
	git config user.name "Grader Check"
	git config commit.gpgsign false
	printf '/.fixture/\n' >>.git/info/exclude
	mkdir -p src .fixture
	printf 'export const label = "converter";\n' >src/page.ts
	printf 'it("says converter", () => {\n  expect(label).toBe("converter");\n});\n' >src/page.test.ts
	git add src
	git commit -q -m base
	git rev-parse HEAD >.fixture/base-sha

	printf 'it("says calculator", () => {\n  expect(label).toBe("calculator");\n});\n' >src/page.test.ts
	printf 'it("is new", () => {});\n' >src/extra.test.ts
	git add -N src/extra.test.ts
	git diff >.fixture/tests.patch
	git checkout -q -- src/page.test.ts
	rm -f src/extra.test.ts
	git reset -q
}

# The answer key's version of every file it names, whatever the agent did.
assert_answer_key_applied() {
	grep -q 'toBe("calculator")' src/page.test.ts || fail "$1: page.test.ts is not the answer key's"
	[[ -f src/extra.test.ts ]] || fail "$1: extra.test.ts was not created"
	grep -q 'it("is new"' src/extra.test.ts || fail "$1: extra.test.ts is not the answer key's"
}

run_case() {
	local name="$1" agent="$2" dir
	dir="$(mktemp -d)"
	(
		setup "${dir}"
		"${agent}"
		bash "${GRADER}" >/dev/null 2>&1 || fail "${name}: the grader did not apply tests.patch"
		assert_answer_key_applied "${name}"
		if [[ "${name}" != clean ]]; then
			grep -q '"calculator"' src/page.ts || fail "${name}: the agent's implementation change was lost"
		fi
	)
	rm -rf "${dir}"
	echo "  ok  ${name}"
}

agent_same_hunk() {
	printf 'export const label = "calculator";\n' >src/page.ts
	printf 'it("says calculator", () => {\n  expect(label).toContain("calc");\n});\n' >src/page.test.ts
}

agent_new_file() {
	agent_same_hunk
	printf 'it("is the agent'\''s own", () => {});\n' >src/extra.test.ts
}

agent_committed() {
	agent_new_file
	git add src
	git commit -q -m "agent's work"
}

agent_clean() {
	:
}

run_case same-hunk agent_same_hunk
run_case new-file agent_new_file
run_case committed agent_committed
run_case clean agent_clean
echo "check-model-classes-grader: 4 case(s) pass"
