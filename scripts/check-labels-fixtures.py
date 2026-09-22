#!/usr/bin/env python3
"""Exercise the supplemental-label parser with deterministic offline fixtures.

`check-labels.py` compares the repository's real skill and Tofu files. That
proves today's copies agree, but it cannot prove that both marked tables remain
part of the comparison. These fixtures load the checker, substitute temporary
skill and Tofu files, and hold the silent failures in place: a supplemental
label missing from Tofu, description drift, a duplicate table name, and a
shared colour all fail.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-labels.py"

SKILL_TEXT = """<!-- issue-kind-labels-table -->

| Label | Description | Ready |
| ----- | ----------- | ----- |
| `epic` | Coordinates work | No |
| `task` | Discrete work | Yes |

<!-- supplemental-labels-table -->

| Label | Description | Meaning |
| ----- | ----------- | ------- |
| `story` | A focused piece of work within an epic | Visual |
"""


def label(resource: str, name: str, description: str, colour: str) -> str:
    """Return one minimal GitHub label resource fixture."""
    return f'''resource "github_issue_label" "{resource}" {{
  name        = "{name}"
  description = "{description}"
  color       = "{colour}"
}}
'''


TF_TEXT = "".join(
    (
        label("epic", "epic", "Coordinates work", "5319e7"),
        label("task", "task", "Discrete work", "0e8a16"),
        label("story", "story", "A focused piece of work within an epic", "d4c5f9"),
    )
)


def load_checker():
    """Load the hyphenated checker module without running its main function."""
    spec = importlib.util.spec_from_file_location("check_labels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(module, skill_text: str, tf_text: str) -> tuple[int, str]:
    """Run the checker against one temporary skill and Tofu fixture pair."""
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        skill = root / "SKILL.md"
        labels_tf = root / "labels.tf"
        skill.write_text(skill_text, encoding="utf-8")
        labels_tf.write_text(tf_text, encoding="utf-8")
        original_skill, original_labels_tf = module.SKILL, module.LABELS_TF
        module.SKILL, module.LABELS_TF = skill, labels_tf
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                result = module.main()
        finally:
            module.SKILL, module.LABELS_TF = original_skill, original_labels_tf
        return result, stderr.getvalue()


def require(condition: bool, message: str) -> None:
    """Fail this fixture run with an actionable message."""
    if not condition:
        raise AssertionError(message)


def main() -> int:
    checker = load_checker()
    rows = checker.parse_skill_tables(SKILL_TEXT)
    require(
        rows == [
            ("epic", "Coordinates work"),
            ("task", "Discrete work"),
            ("story", "A focused piece of work within an epic"),
        ],
        f"supplemental table was not parsed: {rows}",
    )

    cases = (
        ("agreement", SKILL_TEXT, TF_TEXT, 0, ""),
        (
            "missing supplemental declaration",
            SKILL_TEXT,
            TF_TEXT.replace(label("story", "story", "A focused piece of work within an epic", "d4c5f9"), ""),
            1,
            "`story` is in the skill's table but not declared",
        ),
        (
            "supplemental description drift",
            SKILL_TEXT,
            TF_TEXT.replace("A focused piece of work within an epic", "Different description", 1),
            1,
            "`story` has two descriptions",
        ),
        (
            "duplicate table name",
            SKILL_TEXT.replace("`story`", "`task`"),
            TF_TEXT,
            1,
            "`task` appears more than once in the skill's label tables",
        ),
        (
            "duplicate colour",
            SKILL_TEXT,
            TF_TEXT.replace('color       = "d4c5f9"', 'color       = "5319e7"'),
            1,
            "`story` and `epic` share the colour 5319e7",
        ),
    )
    for name, skill_text, tf_text, expected_status, expected_message in cases:
        status, stderr = run(checker, skill_text, tf_text)
        require(status == expected_status, f"{name}: expected {expected_status}, got {status}")
        if expected_message:
            require(expected_message in stderr, f"{name}: missing `{expected_message}`: {stderr}")

    print("label checker fixtures: supplemental label scenarios passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
