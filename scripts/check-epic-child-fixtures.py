#!/usr/bin/env python3
"""Verify offline epic-child reconciliation scenarios.

Skills are prose, so live GitHub writes cannot prove this contract safely. These
fixtures model only the inputs that the skills must distinguish: a confirmed
parent's labels, an unavailable graph read, closure, the existing kind, and
unrelated labels. They lock down the marker policy without creating a label or
changing an edge on GitHub.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "scripts" / "fixtures" / "epic-child-labels.json"
KINDS = frozenset({"epic", "task", "bug", "proposal", "research", "human"})
READY_KINDS = frozenset({"task", "bug", "research"})
MARKER = "epic-child"


def reconcile(labels: list[str], parent_labels: list[str], graph_read: str) -> tuple[list[str], str]:
    """Return labels and action for one direct-parent reconciliation read."""
    if graph_read != "confirmed":
        return labels, "preserve"
    qualifies = "epic" in parent_labels
    has_marker = MARKER in labels
    if qualifies and not has_marker:
        return [*labels, MARKER], "add"
    if not qualifies and has_marker:
        return [label for label in labels if label != MARKER], "remove"
    return labels, "keep"


def classify(labels: list[str]) -> str:
    """Return the readiness classification unaffected by the supplemental marker."""
    kinds = [label for label in labels if label in KINDS]
    if len(kinds) == 0:
        return "unclassified"
    if len(kinds) > 1:
        return "conflicting kinds"
    return "ready" if kinds[0] in READY_KINDS else "not ready"


def main() -> int:
    cases = json.loads(FIXTURES.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        labels, action = reconcile(
            case["labels"], case["parent_labels"], case["graph_read"]
        )
        if labels != case["expected_labels"]:
            failures.append(f'{case["name"]}: labels {labels!r}')
        if action != case["expected_action"]:
            failures.append(f'{case["name"]}: action {action!r}')
        classification = classify(labels)
        if classification != case["expected_classification"]:
            failures.append(f'{case["name"]}: classification {classification!r}')
    if failures:
        print("epic-child fixture failures:", file=sys.stderr)
        print(*[f"  - {failure}" for failure in failures], sep="\n", file=sys.stderr)
        return 1
    print(f"epic-child fixtures: {len(cases)} reconciliation scenarios passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
