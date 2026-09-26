#!/usr/bin/env python3
"""Check Omp's documented draft PR creation route without GitHub credentials."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFERENCES = (
    ROOT / "skills" / "pr" / "references" / "omp.md",
    ROOT / "skills" / "pr-title" / "references" / "omp.md",
    ROOT / "skills" / "pr-body" / "references" / "omp.md",
)
REQUIRED_ROUTE = 'gh pr create --draft --title "<title>" --body-file <path>'
UNSUPPORTED_FIXTURE = "The `github` tool's `pr_create` op opens a draft pull request."


def unsupported_required_call(text: str) -> bool:
    """Return whether a reference requires the unavailable Omp GitHub tool."""
    normalized = " ".join(text.split())
    return "github.pr_create" in normalized or "`github` tool" in normalized


def validate_reference(text: str) -> str | None:
    """Return the route violation, or None when the supported route is present."""
    if unsupported_required_call(text):
        return "requires unavailable github.pr_create"
    if f"`{REQUIRED_ROUTE}`" not in " ".join(text.split()):
        return f"does not document `{REQUIRED_ROUTE}` as a command"
    return None


def fail(message: str) -> None:
    """Print one assertion failure and terminate with a nonzero status."""
    print(f"check-omp-pr-create-route: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    """Reject unsupported or inconsistent Omp pull-request creation routes."""
    if not unsupported_required_call(UNSUPPORTED_FIXTURE):
        fail("unsupported-route fixture does not identify github.pr_create")
    if validate_reference(UNSUPPORTED_FIXTURE) is None:
        fail("unsupported-route fixture was accepted")

    for path in REFERENCES:
        error = validate_reference(path.read_text(encoding="utf-8"))
        if error:
            fail(f"{path.relative_to(ROOT)} {error}")

    print(
        "check-omp-pr-create-route: all Omp references use the supported draft gh route"
    )


if __name__ == "__main__":
    main()
