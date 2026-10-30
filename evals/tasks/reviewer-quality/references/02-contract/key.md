# Expected review

- Trigger: `service.py` returns `balance_cents`; `client.py` still indexes `balance`.
- Impact: every summary call fails with `KeyError`.
- Valid location: `client.py`, the stale field access.
- Expected verdict: report a consumer-visible cross-file contract defect.
