#!/usr/bin/env python3
"""Build runs/667-merged: 200 logical slots from the original run plus the
four rerun directories (#667). Copies only; the sources are never modified.

Original slots that were not limit-crashed keep their place. The 87
limit-crashed slots are replaced by the rerun result named in mapping.json.
"""
import json, shutil
from pathlib import Path

runs = Path("runs")
orig = runs / "2026-10-31_09-58-44"
out = runs / "667-merged"
here = Path("provenance/667-rerun")
mapping = json.loads((here / "mapping.json").read_text())
ledger = json.loads((here / "original-ledger.json").read_text())
replace = {(m["variant"], m["case"], m["original_repeat"]): m for m in mapping}
assert len(replace) == 87
assert not out.exists()

run = json.loads((orig / "run.json").read_text())
rerun_rows = {}
for g in sorted({m["group"] for m in mapping}):
    for row in json.loads((runs / f"667-rerun-{g}" / "run.json").read_text())["task_results"]:
        rerun_rows[(g, row["variant_id"], row["task_id"], row["replicate_index"])] = row

# Slot directories.
for s in ledger:
    key = (s["variant"], s["case"], s["repeat"])
    dst = out / s["variant"] / s["case"] / f"{s['repeat']:02d}"
    m = replace.get(key)
    src = (runs / f"667-rerun-{m['group']}" / m["variant"] / m["case"] / f"{m['local_repeat']:02d}") if m else (orig / s["variant"] / s["case"] / f"{s['repeat']:02d}")
    shutil.copytree(src, dst)

# run.json: replace the 87 rows, keep original order.
rows = []
for row in run["task_results"]:
    key = (row["variant_id"], row["task_id"], row["replicate_index"])
    m = replace.get(key)
    if m:
        new = dict(rerun_rows[(m["group"], m["variant"], m["case"], m["local_repeat"])])
        new["replicate_index"] = m["original_repeat"]
        row = new
    rows.append(row)
assert len(rows) == 200
run["task_results"] = rows
run["tasks_run"] = len(rows)
for k, st in (("tasks_succeeded", "SUCCESS"), ("tasks_failed", "FAILURE"), ("tasks_error", "ERROR")):
    run[k] = sum(r["status"] == st for r in rows)
run["pass_rate"] = round(run["tasks_succeeded"] / len(rows), 3)
run["error_share"] = round(run["tasks_error"] / len(rows), 3)
run["merged_from"] = {"original": str(orig), "reruns": sorted(f"667-rerun-{g}" for g in {m["group"] for m in mapping}), "mapping": str(here / "mapping.json")}
run["end_time"] = max(json.loads((runs / f"667-rerun-{g}" / "run.json").read_text())["end_time"] for g in {m["group"] for m in mapping})
out.mkdir(exist_ok=True)
(out / "run.json").write_text(json.dumps(run, indent=2))

# experiment.json: per-replicate scores rebuilt from the merged rows.
exp = json.loads((orig / "experiment.json").read_text())
scores = {}
for r in sorted(rows, key=lambda r: r["replicate_index"]):
    scores.setdefault(r["variant_id"], {}).setdefault(r["task_id"], []).append(r["weighted_score"])
exp["per_replicate_scores"] = scores
for k in ("variant_aggregates", "task_summaries"):
    exp.pop(k, None)
exp["merged_from"] = run["merged_from"]
(out / "experiment.json").write_text(json.dumps(exp, indent=2))
shutil.copy(orig / "resume_fingerprint.json", out / "resume_fingerprint.json")
print(run["tasks_run"], run["tasks_succeeded"], run["tasks_failed"], run["tasks_error"])
