#!/usr/bin/env bash
# Re-run exactly the 87 limit-crashed slots of runs/2026-10-31_09-58-44 (#667).
# Run from the repository root. Reads plan.json; mapping.json maps local
# repeats back to the original logical slots. Never touches the original run.
set -uo pipefail
unset GH_TOKEN GITHUB_TOKEN BASH_DEFAULT_TIMEOUT_MS BASH_MAX_TIMEOUT_MS
cd evals
python3 -I - <<'P' | while IFS='|' read -r group variant k tasks; do
import json
for p in json.load(open('provenance/667-rerun/plan.json')):
    print(f"{p['group']}|{p['variant']}|{p['repeats']}|{' '.join(p['tasks'])}")
P
  TELEMETRY_ENABLED=false uv tool run --isolated --python 3.13 --from coder-eval==0.11.6 \
    --with-editable "$PWD/coder-eval-omp" --with-editable "$PWD/coder-eval-codex" \
    coder-eval run --max-parallel 8 --repeats "$k" \
    -e "experiments/with-without-667-rerun-${variant}.yaml" \
    --run-dir "runs/667-rerun-${group}" \
    --exclude-tags omp-only,codex-only,skip:claude,model-classes $tasks
  echo "group ${group} exit $?"
done
