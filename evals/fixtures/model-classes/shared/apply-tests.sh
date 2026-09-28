#!/usr/bin/env bash
#
# Applies the pull request's own tests over the tree the agent leaves behind.
# Run as the grading `run_command`, against the sandbox root, after the
# deletion and skip checks have read the agent's own tree.
#
# `tests.patch` is a diff from the base SHA, so it applies only to its paths
# as they were at the base. An agent that does what its instructions require --
# a test beside the change -- has usually edited those very files, and a plain
# `git apply` then refuses the patch and scores a correct change 0. So each
# path the patch names is first put back to the base commit recorded in
# `.fixture/base-sha`, or removed where the base had no such file, and the
# patch then applies as it did at build time. The agent's own tests in other
# files stay, and the criterion keeps meaning "the pull request's tests pass".

set -euo pipefail

patch=".fixture/tests.patch"
base="$(<.fixture/base-sha)"

while IFS= read -r path; do
	[[ -z "${path}" ]] && continue
	if git cat-file -e "${base}:${path}" 2>/dev/null; then
		git checkout -q "${base}" -- "${path}"
	else
		rm -f -- "${path}"
	fi
done < <(sed -n -E 's|^diff --git a/(.+) b/(.+)$|\1\n\2|p' "${patch}" | sort -u)

git apply --whitespace=nowarn "${patch}"
