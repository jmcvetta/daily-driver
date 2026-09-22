#!/usr/bin/env bash
#
# Fails when a test file carries more skip/xfail markers than it did at the
# base SHA. `.fixture/base-skip-counts.txt` is `<count><TAB><path>` per base
# test file, written by `scripts/evals-cases-from-prs.py`. The pattern covers
# pytest's decorator and call forms and the common JS/TS `.skip(`/`it.skip`/
# `describe.skip` idioms; a marker style outside that list is not counted, in
# either direction, so this check is a floor rather than a proof. Run as a
# `run_command` success criterion, against the sandbox root, before
# `tests.patch` is applied -- a marker the agent added is a fact about its
# own tree, not about the grading patch.

set -euo pipefail

manifest=".fixture/base-skip-counts.txt"
if [[ ! -r "${manifest}" ]]; then
	echo "no manifest at ${manifest}" >&2
	exit 1
fi

pattern='@pytest\.mark\.(skip|xfail)|pytest\.skip\(|\.skip\(|\bxfail\s*=|\bit\.skip\(|\bdescribe\.skip\('

fail=0
while IFS=$'\t' read -r base_count path; do
	[[ -z "${path}" ]] && continue
	# A deleted file is the other check's finding, not this one's.
	[[ -e "${path}" ]] || continue
	current_count="$(grep -Eic "${pattern}" "${path}" || true)"
	if ((${current_count:-0} > ${base_count:-0})); then
		echo "new skip/xfail marker in: ${path} (was ${base_count}, now ${current_count})"
		fail=1
	fi
done <"${manifest}"

exit "${fail}"
