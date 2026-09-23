#!/usr/bin/env bash
#
# Clones a source repository's base commit into the sandbox root, shallow, so
# nothing after it is visible to the agent under test. Sourced, never
# executed. A case script is
#     source "$(dirname "$0")/lib.sh"
#     fixture_clone_base owner/repo <base-sha>
# See `evals/README.md` for what depends on this shape.

set -euo pipefail

FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SANDBOX_DIR="$(cd "${FIXTURE_DIR}/.." && pwd)"

# Shallow-fetch one commit of `owner/repo` and check it out at the sandbox
# root. Depth 1 is what keeps "beyond that commit" out of the checkout --
# there is no history to strip because none was ever fetched. Credentials
# come from the host environment (GITHUB_TOKEN or GH_TOKEN): the `tempdir`
# driver every task in this suite uses runs pre_run as a plain host process,
# so a token exported before `coder-eval run` is already in this shell's
# environment.
fixture_clone_base() {
	local slug="$1" sha="$2" token
	cd "${SANDBOX_DIR}"
	token="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
	if [[ -z "${token}" ]]; then
		echo "fixture_clone_base: GITHUB_TOKEN or GH_TOKEN must be set to clone ${slug}" >&2
		return 1
	fi

	git init -q .
	# Keep the fixture's own scripts out of the checked-out tree's status, the
	# same way review-depth's fixture keeps `.fixture/` out of its diff.
	printf '/.fixture/\n' >>.git/info/exclude
	git config user.email "eval@example.invalid"
	git config user.name "Eval Fixture"
	git config commit.gpgsign false

	git remote add origin "https://x-access-token:${token}@github.com/${slug}.git"
	git fetch -q --depth 1 origin "${sha}"
	git checkout -q FETCH_HEAD
}
