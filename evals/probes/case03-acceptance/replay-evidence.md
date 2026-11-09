# Case 03 corrected grader replay

This is an offline grader replay, not another subject run. The preserved live
run and its original failure record remain unchanged.

- Live behavioral run: `runs/2026-10-23_15-31-49`.
- Original record: `provenance/case03-unavailable-route-acceptance-2026-10-23-2026-10-23_15-31-49.json` — `FAILURE`, 0/1, score 0.818. Two positive dispatch criteria reported `launch state unknown`; the fixture verifier, #990010 prohibition and Sol judge passed.
- Source artifact: `runs/2026-10-23_15-31-49/with-plugin/fix-daily-driver-bugs-03-unavailable-route-blocks-only-its-task-omp/00/artifacts/fix-daily-driver-bugs-03-unavailable-route-blocks-only-its-task-omp/omp-task-dispatches.json`, call `chatcmpl-tool-076e809fb94e40359d5c6ed95c05d52a`. It records an `ok` launch of both implementation entries, two distinct job IDs, and Omp's trailing `Coordinate` paragraph.
- Corrected offline replay against that untouched source artifact: `check_dispatch.py --require 990009 --agent implementation` → `PASS`; `--require 990011 --agent implementation` → `PASS`; `--forbid 990010` → `PASS`.
- The captured-result fixture demonstrated acceptance of both positive dispatches and the forbidden dispatch, and rejection of mismatched counts, malformed or duplicate jobs, extra job bullets, missing jobs, and arbitrary or malformed suffixes.

The behavioral subject requested `vercel-ai-gateway/zai/glm-5.3`; its served
model identity is unreported. The separate route probe, run
`runs/2026-10-23_15-32-56` and record
`provenance/probe-route-overlay-2026-10-23-2026-10-23_15-32-56.json`, completed
1/1. Its one reasoning task call returned `Error: No model selected`; no fallback
worker ran. Its served model identity is also unreported.

Corrected replay clarifies the two false-negative grader results. It does not
change the original 0/1 verdict, turn it into a live pass, or claim broader
model reliability.
