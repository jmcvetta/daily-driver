# Expected review

- Trigger: `transfer` debits the source twice but credits the target once.
- Impact: each transfer destroys an extra amount from the source wallet.
- Valid location: `wallet.py`, the duplicate debit.
- Expected verdict: report a data-integrity/funds-loss defect.
