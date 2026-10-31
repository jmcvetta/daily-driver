# Expected review

- Trigger: `service.py` returns `balance_cents`; `client.py` still indexes `balance`.
- Impact: every summary call fails with `KeyError`.
- Valid location: the changed `balance_cents` field in `service.py` or the stale `balance` access in `client.py`.
- Expected verdict: report a consumer-visible cross-file contract defect.
