#!/usr/bin/env python3
"""The label standard is written twice, so the two copies are checked.

`skills/issue-labels/SKILL.md` carries the tables a session reads: six
mutually-exclusive issue kinds and supplemental visual markers.
`infra/github/labels.tf` carries the `github_issue_label` resources GitHub is
configured from. A label's description is the same string in both, because the
skill is what Claude reads and GitHub is what a person hovers, and a standard
that says one thing in each is not a standard.

Nothing else would catch the drift. `claude plugin validate` never opens a
`.tf` file, `tofu validate` never opens a skill, and a table row that has
fallen behind the Tofu reads exactly like one that has not -- it is prose, and
it is still well-formed. The failure is silent in both directions: a label
declared in Tofu and missing from the tables is one no session will ever apply,
and a label in a table and missing from Tofu is one an apply will not create.

WHAT IT ASSERTS

    The same set of label names in the tables and Tofu.
    The same description for every name.
    No duplicate label name across either skill table or Tofu resource.
    A non-empty colour on every Tofu resource, and no two labels sharing one.

WHAT IT DOES NOT ASSERT

    That the labels exist on GitHub. Only an apply puts them there, and this
    script is credential-free on purpose -- it runs from a Makefile on a
    laptop and from CI, and neither has a token with admin rights.

No third-party imports, for the reason `check-manifests.py` gives: a
dependency install between the laptop and CI is a place for them to differ.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL = ROOT / "skills" / "issue-labels" / "SKILL.md"
LABELS_TF = ROOT / "infra" / "github" / "labels.tf"

# Tables are found by marker rather than position, so prose may move without
# silently moving what is parsed. Each table ends at its first blank line.
TABLE_MARKERS = (
    "<!-- issue-kind-labels-table -->",
    "<!-- supplemental-labels-table -->",
)

# | `name` | description | anything |
TABLE_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|")

# resource "github_issue_label" "epic" { ... }. The resource's own label is
# captured as well as its body: two resources declaring one `name` is a
# duplicate Tofu rejects at apply time, and naming both halves of the pair is
# what lets this script say which two.
TF_RESOURCE = re.compile(
    r'resource\s+"github_issue_label"\s+"([^"]+)"\s*\{(.*?)^\}',
    re.DOTALL | re.MULTILINE,
)
TF_ATTR = re.compile(r'^\s*(\w+)\s*=\s*"([^"]*)"\s*$', re.MULTILINE)


def parse_skill_tables(text: str) -> list[tuple[str, str]]:
    """Return (label name, description) rows from every marked skill table."""
    rows: list[tuple[str, str]] = []
    for marker in TABLE_MARKERS:
        start = text.find(marker)
        if start < 0:
            sys.exit(f"{SKILL}: no {marker} marker; nothing to check against")

        table_rows: list[tuple[str, str]] = []
        for line in text[start + len(marker):].splitlines():
            if table_rows and not line.startswith("|"):
                break
            match = TABLE_ROW.match(line)
            if match:
                table_rows.append((match.group(1), match.group(2)))
        if not table_rows:
            sys.exit(f"{SKILL}: the table after {marker} has no rows")
        rows.extend(table_rows)
    return rows


def parse_labels_tf(text: str) -> list[tuple[str, str, str, str]]:
    """Return one (resource, name, description, colour) row per Tofu resource.

    A list rather than a dict keyed on the label name, because two resources
    declaring one `name` is a real failure and a dict would swallow it: the
    second row would overwrite the first, the set comparison would still
    match the skill's table, and the apply would be the thing that discovered
    the duplicate.
    """
    rows: list[tuple[str, str, str, str]] = []
    for resource, body in TF_RESOURCE.findall(text):
        attrs = dict(TF_ATTR.findall(body))
        name = attrs.get("name")
        if not name:
            sys.exit(
                f"{LABELS_TF}: github_issue_label.{resource} declares no name"
            )
        rows.append(
            (resource, name, attrs.get("description", ""), attrs.get("color", ""))
        )
    if not rows:
        sys.exit(f"{LABELS_TF}: no github_issue_label resources found")
    return rows


def main() -> int:
    table_rows = parse_skill_tables(SKILL.read_text(encoding="utf-8"))
    rows = parse_labels_tf(LABELS_TF.read_text(encoding="utf-8"))

    problems: list[str] = []

    # Duplicates first, and by resource rather than by label name, so the two
    # collapsing rows are both reported before anything reads them as one.
    by_name: dict[str, str] = {}

    table: dict[str, str] = {}
    for name, description in table_rows:
        if name in table:
            problems.append(
                f"`{name}` appears more than once in the skill's label tables"
            )
        else:
            table[name] = description
    for resource, name, _, _ in rows:
        if name in by_name:
            problems.append(
                f"github_issue_label.{resource} and "
                f"github_issue_label.{by_name[name]} both declare the label "
                f"`{name}`; the apply fails on the second"
            )
        else:
            by_name[name] = resource

    declared = {name: description for _, name, description, _ in rows}
    colours = {name: colour for _, name, _, colour in rows}

    for name in sorted(set(table) - set(declared)):
        problems.append(
            f"`{name}` is in the skill's table but not declared in labels.tf, "
            f"so an apply will not create it"
        )
    for name in sorted(set(declared) - set(table)):
        problems.append(
            f"`{name}` is declared in labels.tf but missing from the skill's "
            f"table, so no session will ever apply it"
        )
    for name in sorted(set(table) & set(declared)):
        if table[name] != declared[name]:
            problems.append(
                f"`{name}` has two descriptions:\n"
                f"    skill: {table[name]}\n"
                f"    tofu:  {declared[name]}"
            )

    # Colours are checked per resource, not per label name, for the same
    # reason: a duplicate name must not hide one of the two colours.
    seen: dict[str, str] = {}
    for resource, name, _, colour in rows:
        if not colour:
            problems.append(
                f"github_issue_label.{resource} (`{name}`) declares no colour"
            )
            continue
        if colour in seen and seen[colour] != name:
            problems.append(
                f"`{name}` and `{seen[colour]}` share the colour {colour}; "
                f"a label is told apart by it"
            )
        else:
            seen.setdefault(colour, name)

    if problems:
        print("the label standard disagrees with itself:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    print(f"label standard: {len(table)} labels agree between the skill and the Tofu")
    return 0


if __name__ == "__main__":
    sys.exit(main())
