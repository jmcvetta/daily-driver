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
# A last case runs the grader with no `REFERENCE_DIR` and requires it to fail:
# a grader that found no answer key and exited 0 would pass every replicate.
#
# One more case checks the clone, not the grader: `clone-base.sh` must remove
# the `origin` remote once it has fetched, or `git fetch origin <branch>`
# hands the agent the merged change. A `git` shim on PATH records the calls,
# so the case needs no network.
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
# state into the reference directory `$2`, and leave the working tree at the
# base with `.fixture/` in place -- the layout a run gives the grader.
setup() {
	local dir="$1" reference="$2"
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
	git diff >"${reference}/tests.patch"
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
	local name="$1" agent="$2" dir reference
	dir="$(mktemp -d)"
	reference="$(mktemp -d)"
	(
		setup "${dir}" "${reference}"
		"${agent}"
		REFERENCE_DIR="${reference}" bash "${GRADER}" >/dev/null 2>&1 ||
			fail "${name}: the grader did not apply tests.patch"
		assert_answer_key_applied "${name}"
		if [[ "${name}" != clean ]]; then
			grep -q '"calculator"' src/page.ts || fail "${name}: the agent's implementation change was lost"
		fi
	)
	rm -rf "${dir}" "${reference}"
	echo "  ok  ${name}"
}

# Without `REFERENCE_DIR` there is no answer key, and the grader must say so
# by failing rather than grade the agent's tree as it stands.
no_reference() {
	local dir reference
	dir="$(mktemp -d)"
	reference="$(mktemp -d)"
	(
		setup "${dir}" "${reference}"
		agent_same_hunk
		if env -u REFERENCE_DIR bash "${GRADER}" >/dev/null 2>&1; then
			fail "no-reference: the grader passed with no answer key"
		fi
	)
	rm -rf "${dir}" "${reference}"
	echo "  ok  no-reference"
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
# The clone, run against a `git` shim that logs each call and does nothing.
clone_drops_origin() {
	local dir shim log
	dir="$(mktemp -d)"
	shim="$(mktemp -d)"
	log="${shim}/calls"
	cat >"${shim}/git" <<-SHIM
		#!/usr/bin/env bash
		printf '%s\n' "\$*" >>"${log}"
		[[ "\$1" == init ]] && mkdir -p .git/info
		exit 0
	SHIM
	chmod +x "${shim}/git"
	mkdir -p "${dir}/.fixture"
	cp "${REPO_ROOT}/evals/fixtures/model-classes/shared/"{lib.sh,clone-base.sh} "${dir}/.fixture/"
	(cd "${dir}" && PATH="${shim}:${PATH}" GITHUB_TOKEN=check-token bash .fixture/clone-base.sh owner/repo 0123abc) ||
		fail "clone-drops-origin: clone-base.sh exited non-zero"
	grep -qx 'remote remove origin' "${log}" || fail "clone-drops-origin: origin was never removed"
	[[ "$(grep -n 'remote remove origin' "${log}" | cut -d: -f1)" -gt "$(grep -n '^fetch ' "${log}" | cut -d: -f1)" ]] ||
		fail "clone-drops-origin: origin was removed before the fetch"
	grep -qx '0123abc' "${dir}/.fixture/base-sha" || fail "clone-drops-origin: base-sha was not recorded"
	rm -rf "${dir}" "${shim}"
	echo "  ok  clone-drops-origin"
}

run_case clean agent_clean
no_reference
clone_drops_origin
echo "check-model-classes-grader: 6 case(s) pass"
