# Expected review

- Trigger: `export_project` denies the project owner and permits other users.
- Impact: non-owners can obtain project archives while owners cannot export.
- Valid location: `exports.py`, the reversed owner conditional.
- Expected verdict: report an authorization defect.
