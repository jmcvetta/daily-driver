# Expected review

- Trigger: `page` computes the exclusive end as `offset + limit - 1`, returning one fewer item than requested for positive limits.
- Impact: consumers lose the final requested record and can skip it during pagination.
- Valid location: `records.py`, the end expression in `page`.
- Expected verdict: report a defect.
