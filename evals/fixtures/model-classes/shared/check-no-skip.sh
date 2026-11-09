#!/usr/bin/env bash
#
# Fails when a test file carries more skip/xfail markers than it did at the
# base SHA. `base-skip-counts.txt` is `<count><TAB><path>` per base
# test file, written by `scripts/evals-cases-from-prs.py`. The pattern covers
# pytest's decorator and call forms and the common JS/TS `.skip(`/`it.skip`/
# `describe.skip` idioms; a marker style outside that list is not counted, in
# either direction, so this check is a floor rather than a proof. Run as a
# `run_command` success criterion, against the sandbox root, before
# `tests.patch` is applied -- a marker the agent added is a fact about its
# own tree, not about the grading patch.
#
# The answer key lives in the task's `reference:` directory, which coder_eval
# stages outside the sandbox and names in `REFERENCE_DIR` for criteria only;
# the agent never sees the path.

set -euo pipefail

manifest="${REFERENCE_DIR:?REFERENCE_DIR is unset: run as a criterion of a task with a reference}/base-skip-counts.txt"
if [[ ! -r "${manifest}" ]]; then
	echo "no manifest at ${manifest}" >&2
	exit 1
fi

# `\.skip\(` alone already matches `pytest.skip(`, `it.skip(` and
# `describe.skip(` as substrings, so those three forms are not named again.
pattern='@pytest\.mark\.(skip|xfail)|\.skip\(|\bxfail\s*='

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
