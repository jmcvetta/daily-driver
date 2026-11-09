#!/usr/bin/env python3
"""Assert recorded issue state and GitHub operations for an eval case."""
import json
from pathlib import Path

root = Path.cwd()
state = json.loads((root / "fixture-state.json").read_text(encoding="utf-8"))
expected = json.loads((root / "fixture-expectations.json").read_text(encoding="utf-8"))
actions = [json.loads(line) for line in (root / "issue-actions.jsonl").read_text(encoding="utf-8").splitlines()]
errors = []

for number, contract in expected.get("issues", {}).items():
    item = state["issues"][number]
    if item["title"] != contract["title"]:
        errors.append(f"#{number}: title mismatch")
    if sorted(item["labels"]) != sorted(contract["labels"]):
        errors.append(f"#{number}: labels mismatch")
    for text in contract.get("body_contains", []):
        if text not in item["body"]:
            errors.append(f"#{number}: missing body evidence {text!r}")
    for text in contract.get("body_absent", []):
        if text in item["body"]:
            errors.append(f"#{number}: unexpected body text {text!r}")
    for text in contract.get("comment_contains", []):
        if not any(text in comment.get("body", "") for comment in item.get("comments", [])):
            errors.append(f"#{number}: missing comment evidence {text!r}")

def matches(action, contract):
    fields = contract.get("fields_contains", [])
    exact = {key: value for key, value in contract.items() if key != "fields_contains"}
    return (all(action.get(key) == value for key, value in exact.items())
            and all(field in action.get("fields", []) for field in fields))

for contract in expected.get("required_actions", []):
    if not any(matches(action, contract) for action in actions):
        errors.append(f"missing action {contract!r}")
for contract in expected.get("forbidden_actions", []):
    if any(matches(action, contract) for action in actions):
        errors.append(f"forbidden action {contract!r}")

result = root / "fixture-verification.txt"
if errors:
    result.write_text("FAIL\n" + "\n".join(errors) + "\n", encoding="utf-8")
    raise SystemExit("\n".join(errors))
result.write_text("PASS\n", encoding="utf-8")
print("fixture state and recorded GitHub actions: PASS")
