#!/usr/bin/env python3
"""The acceptance test for the route half of `scripts/check-manifests.py`.

`check-manifests.py` runs against this repository's real tree, so it can prove
that today's skills are clean but not that the guard still catches what it was
built to catch. A pattern that stops matching — a typo in a regex, a rule
renamed out from under its message — is a silent zero: the guard stays green
and lets every harness route back into every description. This script rebuilds
the cases in a temp directory and holds each behaviour in place:

- a foreign route in a folded (`>-`) description is rejected, located in the
  description, and named;
- a route in a body is rejected, located at its real line number, and named;
- neutral trigger prose is accepted;
- public skill invocations (a `/review-cycle`, a `/pr`) are accepted;
- harness names and the reference links that select the active harness's
  reference file are accepted;
- concrete routes inside `references/*.md` are accepted — the guard reads a
  skill's description and body and nothing else;
- every route pattern added with #229 (`gh pr create/edit`,
  `gh issue create/edit`, `pr_create`) is exercised against a description
  carrying it, so a pattern that stops matching fails here by name.

The guard is imported rather than run as a subprocess: `reference_errors()`
takes the skills to check and the root to report against, and the module's
import has no side effects beyond reading its own neighbours. Like every
script leg, this needs nothing but Python and runs offline on a laptop and in
CI alike.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check-manifests.py"

# The patterns #229 added. Each must be exercised against a description
# carrying a live spelling of it, so a pattern that stops matching is named by
# the case that fails.
NEW_ROUTES = {
    "gh pr create/edit": "gh pr create --draft",
    "gh issue route": "gh issue view 5 --json blockedBy",
    "gh probe": "gh auth status",
    "GitHub tool": "Omp's github tool opens the pull request",
    "GitHub relationship operation": "issue_read with get_sub_issues",
    "pr_create op": "the pr_create operation",
}


class Failed(Exception):
    """A case that did not hold. The message is the report."""


def load_guard():
    """`check-manifests.py`, imported from its hyphenated file.

    The module imports `stanza`, its own neighbour, so the scripts directory
    is put on the path first rather than hoping the caller ran from there.
    """
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("check_manifests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_skill(
    root: Path,
    *,
    description: str,
    body: str,
    references: dict[str, str] | None = None,
) -> Path:
    """One fixture skill, written under `root`, with its path back."""
    skill = root / "skills" / "fixture-skill" / "SKILL.md"
    if skill.parent.exists():
        shutil.rmtree(skill.parent)
    skill.parent.mkdir(parents=True)
    lines = ["---", "name: fixture-skill", "description: >-"]
    lines.extend(f"  {line}" if line else "" for line in description.splitlines())
    lines.extend(["---", ""])
    lines.extend(body.splitlines())
    skill.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for name, content in (references or {}).items():
        target = skill.parent / "references" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return skill


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def main() -> int:
    errors: list[str] = []
    guard = load_guard()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        # 1. A foreign route inside a folded description. The route is split
        #    across two source lines, so only the unfolded string carries it —
        #    this is the case that proves `frontmatter()` folding is reused
        #    rather than the raw text being scanned.
        skill = write_skill(
            root,
            description=(
                "This skill fires whenever a pull request is opened, including\n"
                "any call to `gh pr\n"
                "create` or its friends."
            ),
            body="# Fixture\n\nRead the reference file for the harness in use.\n",
        )
        found = guard.reference_errors([skill], root=root)
        require(len(found) == 1, f"case 1 (folded description): expected 1 error, got {found}")
        require(
            "in the description" in found[0],
            f"case 1: error does not locate the route in the description: {found[0]}",
        )
        require(
            "gh pr create/edit" in found[0] and "(gh pr create)" in found[0],
            f"case 1: error does not name the offending route: {found[0]}",
        )
        require(
            "skills/fixture-skill/SKILL.md" in found[0],
            f"case 1: error does not name the skill path: {found[0]}",
        )

        # 2. A route in the body is still rejected, located at its real line
        #    number. The route lands on file line 11 -- the four frontmatter
        #    lines, the closing `---`, a blank, a heading, prose, a blank --
        #    and the error must say 11 rather than a body-relative 4, which
        #    is the offset arithmetic being held.
        skill = write_skill(
            root,
            description="Fires whenever a pull request is opened for the branch.",
            body=(
                "# Fixture\n\n"
                "Open the pull request through the reference file.\n\n"
                "Or run gh pr create --draft directly.\n"
            ),
        )
        found = guard.reference_errors([skill], root=root)
        require(len(found) == 1, f"case 2 (body route): expected 1 error, got {found}")
        require(
            ":11:" in found[0],
            f"case 2: error does not carry the body's real line number 11: {found[0]}",
        )
        require(
            "in the body" in found[0],
            f"case 2: error does not locate the route in the body: {found[0]}",
        )

        # 3. Neutral acceptance: trigger prose in words, harness names that
        #    only select a reference file, the three reference links, and
        #    reference files holding the concrete calls the prose defers to.
        neutral_description = (
            'Fires on "/fixture-skill", on "open the pull request", and when\n'
            "a pull request is created or updated beyond its title or body\n"
            "alone — on Claude Code, on Oh My Pi and on Codex alike."
        )
        routes = (
            "# Fixture routes\n\n"
            "- Claude Code: call mcp__github__create_pull_request\n"
            "- Omp: the github tool's pr_create op\n"
            "- Codex: run gh pr create\n"
            "- And never AskUserQuestion\n"
        )
        skill = write_skill(
            root,
            description=neutral_description,
            body=(
                "# Fixture\n\n"
                "The routes are per harness, and they live beside this file:\n"
                "[`references/claude.md`](references/claude.md) for Claude Code,\n"
                "[`references/omp.md`](references/omp.md) for Oh My Pi,\n"
                "[`references/codex.md`](references/codex.md) for Codex. Read\n"
                "the one for the harness in use before the first call.\n"
            ),
            references={
                "claude.md": routes + "\n- Model: GPT-5.6 Terra\n",
                "omp.md": routes,
                "codex.md": routes,
            },
        )
        found = guard.reference_errors([skill], root=root)
        require(found == [], f"case 3 (neutral skill): expected no errors, got {found}")
        found = guard.shared_guidance_errors([skill], root=root)
        require(
            found == [],
            f"case 3 (harness exceptions): expected no errors, got {found}",
        )

        # 4. Model identities are rejected in every shared surface. The
        #    description case is folded, so it also exercises `frontmatter()`.
        skill = write_skill(
            root,
            description="A DeepSeek\nV4 route is selected here.",
            body="# Fixture\n",
        )
        found = guard.shared_guidance_errors([skill], root=root)
        require(
            len(found) == 1 and "description" in found[0],
            f"case 4 (folded description): expected one description error, got {found}",
        )

        skill = write_skill(
            root,
            description="A neutral skill description.",
            body="# Fixture\n\nA Claude session runs this body.\n",
        )
        found = guard.shared_guidance_errors([skill], root=root)
        require(
            len(found) == 1 and "the body" in found[0] and ":9:" in found[0],
            f"case 4 (skill body): expected one body error, got {found}",
        )

        rule = root / "rules" / "fixture.md"
        rule.parent.mkdir(exist_ok=True)
        rule.write_text("An OpenAI route is not shared guidance.\n", encoding="utf-8")
        found = guard.shared_guidance_errors([skill], root=root)
        require(
            len(found) == 2 and "rules/fixture.md:1" in found[0],
            f"case 4 (shared rule): expected rule and body errors, got {found}",
        )

        skill = write_skill(
            root,
            description="A neutral skill description.",
            body=(
                "# Fixture\n\n"
                "Read [`references/model-classes.md`](references/model-classes.md).\n"
            ),
            references={"model-classes.md": "DeepSeek V4 is a concrete model.\n"},
        )
        found = guard.shared_guidance_errors([skill], root=root)
        require(
            len(found) == 2
            and "references/model-classes.md:1" in found[1],
            f"case 4 (shared reference): expected rule and reference errors, got {found}",
        )

        shutil.rmtree(rule.parent)

        # 5. Every pattern added with #229 is exercised: a description
        #    carrying each one is rejected, and the error names that rule.
        for name, spelling in NEW_ROUTES.items():
            skill = write_skill(
                root,
                description=(
                    "Fires on a pull request being opened, including any call\n"
                    f"to {spelling}, on any harness."
                ),
                body="# Fixture\n\nRead the reference file for the harness in use.\n",
            )
            found = guard.reference_errors([skill], root=root)
            require(
                len(found) == 1,
                f"case 4 ({name}): expected 1 error for `{spelling}`, got {found}",
            )
            # The message reports the spelling the pattern matched, which for
            # a prefix rule like `mcp__` is shorter than the fixture's sample.
            matched = guard.ROUTES[name].search(spelling).group(0)
            require(
                name in found[0] and matched in found[0],
                f"case 4: error for `{spelling}` does not name the {name} route: {found[0]}",
            )

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(
        "manifest route and model identity guards behave correctly; "
        f"{7 + len(NEW_ROUTES)} case(s) checked"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
