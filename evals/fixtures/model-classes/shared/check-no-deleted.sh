#!/usr/bin/env bash
#
# Fails when a test file present at the base SHA is missing from the tree the
# agent leaves behind. `.fixture/base-test-files.txt` is one repo-relative
# path per line, written by `scripts/evals-cases-from-prs.py` from the same
# diff that produced `tests.patch`. Run as a `run_command` success criterion,
# against the sandbox root, before `tests.patch` is applied -- deletion is a
# question about the agent's own tree, not about the grading patch.

set -euo pipefail

manifest=".fixture/base-test-files.txt"
if [[ ! -r "${manifest}" ]]; then
	echo "no manifest at ${manifest}" >&2
	exit 1
fi

fail=0
while IFS= read -r path; do
	[[ -z "${path}" ]] && continue
	if [[ ! -e "${path}" ]]; then
		echo "deleted: ${path}"
		fail=1
	fi
done <"${manifest}"

exit "${fail}"
