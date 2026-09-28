# Production provenance

Per-model rework mined from `undertake`'s claim and first-readiness comments and `review-cycle`'s `Review verification` comments, by `scripts/model-telemetry.py`. Each pull request under a repository directory here is one JSON record; this table is `render_table` over every record present.

Refresh a repository with `make model-telemetry REPO=owner/repo`, or `python3 scripts/model-telemetry.py owner/repo --refresh` to re-fetch records already on disk.

Sources: jmcvetta/daily-driver.

| Model | PRs | Median elapsed | Median review passes | Findings/PR | Rerun rate |
| --- | --- | --- | --- | --- | --- |
| claude-sonnet-5 | 3 | 32 min | 0 | 0.3 | 100% |
| gpt-5.6-luna | 1 | n/a | 0 | 0.0 | 100% |
| gpt-6-luna | 3 | n/a | 0 | 0.3 | 100% |
| unreported | 65 | n/a | 0 | 0.6 | 92% |
