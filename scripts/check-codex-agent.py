#!/usr/bin/env python3
"""The acceptance test for the Codex eval arm's two silent zeros.

`evals/coder-eval-codex/` teaches `coder_eval` to run the eval suites against
Codex. Almost none of that package can be exercised in `make check`: it needs a
`coder-eval` install and the Codex SDK, and CI here has neither. So the two parts
that decide whether a row scores at all live in
`coder_eval_codex/transcript.py` and `coder_eval_codex/plugins.py`, both of
which import nothing, and this script drives them.

Both failures are silent, and both report zeros that read exactly like a plugin
that never loaded.

`coder_eval` builds the `[RESULT - …]` transcript for its Claude Code agent
alone and hands the judge bare `result_text` from its Codex agent; every rubric
under `evals/tasks/` anchors on that tag and scores 0.0 without it, deliberately
and with no fallback. And `CodexAgent._setup_skills` symlinks each skill by the
plugin path it was handed, so a relative root — which is what an experiment
naturally writes — links fifteen skills that point at themselves.

WHAT IT ASSERTS

    Bare turn text comes back carrying the `[RESULT - …]` anchor, with the
    reply after the tag.
    A crashed turn is tagged ERROR rather than left bare, so a judged row that
    crashed scores 0.0 on the reply rather than on the anchor being missing.
    An empty turn renders exactly what `coder_eval`'s own `format_messages`
    renders for one.
    The rendering is byte-identical to `coder_eval_omp.rpc.render_agent_output`
    for a single block. Two packages render one contract and neither depends on
    the other, so this is what holds them in step; without it one rubric would
    quietly stop reading the same on both harnesses.
    An already-rendered transcript is returned unchanged, so a future
    `coder_eval` that starts tagging its Codex output does not get nested inside
    a second result block.
    A reply that merely quotes the tag is still rendered, so the judge anchors
    on the tag this package wrote rather than on one the model typed.
    A relative plugin root is made absolute before `CodexAgent._setup_skills`
    sees it. That function symlinks each skill by the path it was handed, so a
    relative root makes `.agents/skills/pr -> ../skills/pr` resolve back to the
    link's own directory: fourteen entries, not one of them readable, and a
    treated arm that ran with no skills at full price. `_setup_skills`'s own
    "0 skills linked" warning counts directory entries, so it stays silent on
    it.
    A plugin root that does not resolve to a directory raises rather than
    warning, and so does an entry that is not `type: local`.

WHAT IT DOES NOT ASSERT

    That Codex starts, that a skill is discovered, or that a row fires. The
    first needs the SDK and credentials; the rest need a model, and are what
    `evals/` is for.
    That `skill_triggered` sees a Codex skill engagement. Nothing in this
    repository does that renaming -- the criterion matches the path Codex
    already reads -- so there is nothing here to test. The evidence for that
    claim is in `evals/coder-eval-codex/README.md`.

No third-party imports, for the reason `check-manifests.py` gives: a dependency
install between the laptop and CI is a place for them to differ.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CODEX_SRC = ROOT / "evals" / "coder-eval-codex" / "src"
OMP_SRC = ROOT / "evals" / "coder-eval-omp" / "src"

sys.path.insert(0, str(CODEX_SRC))
sys.path.insert(0, str(OMP_SRC))

from coder_eval_codex.plugins import (  # noqa: E402  (the path inserts must come first)
    PluginPathError,
    resolve_local_plugins,
)
from coder_eval_codex.transcript import (  # noqa: E402
    EMPTY_OUTPUT,
    is_already_tagged,
    render_agent_output,
)
from coder_eval_omp.rpc import render_agent_output as render_omp_output  # noqa: E402


class CheckFailed(Exception):
    """A failed assertion, with the detail that explains it."""


def check(condition: bool, message: str) -> None:
    """Fail the whole script on a false condition, naming what was expected."""
    if not condition:
        raise CheckFailed(message)


def check_anchor_is_written() -> None:
    """Bare Codex turn text comes back with the anchor every rubric reads."""
    rendered = render_agent_output("Off-by-one: the slice excludes its stop index.")
    check(
        rendered.startswith("[ASSISTANT] Off-by-one:"),
        f"the reply must open an assistant block, got {rendered!r}",
    )
    check(
        rendered.rstrip().endswith("[RESULT - SUCCESS] Off-by-one: the slice excludes its stop index."),
        f"the reply must sit after the last [RESULT - ...] tag, got {rendered!r}",
    )


def check_a_crashed_turn_is_tagged_error() -> None:
    """A partial record is tagged rather than left bare."""
    rendered = render_agent_output("half an answer", is_error=True)
    check("[RESULT - ERROR] half an answer" in rendered, f"a failed turn is tagged ERROR, got {rendered!r}")


def check_empty_turns_render_as_coder_eval_renders_them() -> None:
    """Nothing to say is said the same way on every arm."""
    check(render_agent_output("") == EMPTY_OUTPUT, "an empty turn renders as coder_eval renders one")
    check(render_agent_output("   \n  ") == EMPTY_OUTPUT, "a whitespace-only turn is an empty turn")
    check(
        render_agent_output("") == render_omp_output([]),
        "the empty rendering must agree with the Omp arm's, byte for byte",
    )


def check_the_two_arms_render_one_contract() -> None:
    """One block renders identically here and in the Omp arm.

    The two packages must not depend on each other -- a package named for one
    harness has no business being a dependency of another's arm -- so this
    equality is what keeps a single rubric readable on both.
    """
    for text, is_error in (("the answer", False), ("it broke", True), ("line one\nline two", False)):
        mine = render_agent_output(text, is_error=is_error)
        theirs = render_omp_output([text], is_error=is_error)
        check(
            mine == theirs,
            f"the two arms must render {text!r} identically; codex gave {mine!r} and omp gave {theirs!r}",
        )


def check_an_already_rendered_transcript_is_left_alone() -> None:
    """A tagged transcript is not nested inside a second result block."""
    tagged = "[ASSISTANT] narration\n[RESULT - SUCCESS] the answer"
    check(is_already_tagged(tagged), "coder_eval's own transcript shape is recognised")
    check(render_agent_output(tagged) == tagged, "an already-rendered transcript is returned unchanged")


def check_a_reply_quoting_the_tag_is_still_rendered() -> None:
    """The model typing the tag must not become the judge's anchor."""
    quoted = "The harness prints this:\n[RESULT - SUCCESS] whatever"
    check(not is_already_tagged(quoted), "a reply that merely quotes the tag is not a rendered transcript")
    rendered = render_agent_output(quoted)
    check(
        rendered.rstrip().endswith("[RESULT - SUCCESS] whatever"),
        f"the last tag must be the one this package wrote, got {rendered!r}",
    )
    # Three: the quote in the assistant block, ours, and the quote again inside
    # the repeated reply. A judge reading the LAST tag then anchors inside the
    # quote rather than on ours -- which is inherited rather than introduced,
    # because `format_messages` repeats the reply after its own tag and does the
    # same to a Claude reply that quotes it.
    check(
        rendered.count("[RESULT - SUCCESS]") == 3,
        f"the quoted tag stays in the reply and ours is added around it, got {rendered!r}",
    )


def check_a_relative_plugin_root_is_made_absolute() -> None:
    """The self-referential symlink this arm would otherwise link fourteen of."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp).resolve()
        (base / "plugin" / "skills" / "pr").mkdir(parents=True)
        (base / "plugin" / "skills" / "pr" / "SKILL.md").write_text("---\nname: pr\n---\n")
        (base / "evals").mkdir()

        resolved = resolve_local_plugins([{"type": "local", "path": ".."}], base=base / "evals")
        check(
            resolved == [{"type": "local", "path": str(base)}],
            f"a relative root resolves against the base, got {resolved}",
        )

        # And the link that makes, against `_setup_skills`'s own construction.
        for root, expect_readable in ((str(base / "plugin"), True), ("../plugin", False)):
            work = base / f"work-{expect_readable}"
            (work / ".agents" / "skills").mkdir(parents=True)
            link = work / ".agents" / "skills" / "pr"
            link.symlink_to(Path(root) / "skills" / "pr")
            check(
                (link / "SKILL.md").exists() is expect_readable,
                f"a link built from {root!r} must be readable={expect_readable}; "
                "a relative root is what points the link at itself",
            )


def check_a_plugin_root_that_does_not_resolve_raises() -> None:
    """An arm that declared a plugin and loaded none must not run untreated."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp).resolve()
        for entry, why in (
            ({"type": "local", "path": "nowhere"}, "a path that is not a directory"),
            ({"type": "local"}, "an entry with no path"),
            ({"type": "github", "path": "x"}, "an entry that is not `type: local`"),
            ("not-a-mapping", "an entry that is not a mapping"),
        ):
            try:
                resolve_local_plugins([entry], base=base)
            except PluginPathError:
                continue
            raise CheckFailed(f"{why} must raise rather than resolve")

        os.environ.pop("CHECK_CODEX_AGENT_UNSET", None)
        try:
            resolve_local_plugins([{"type": "local", "path": "$CHECK_CODEX_AGENT_UNSET/x"}], base=base)
        except PluginPathError as failure:
            check("env var" in str(failure), f"an unset env var is named as such, got {failure}")
        else:
            raise CheckFailed("an unexpanded env var in a plugin path must raise")


def main() -> None:
    for name, checker in sorted(globals().items()):
        if name.startswith("check_") and callable(checker):
            checker()
    print("check-codex-agent: the Codex arm renders the judge's transcript anchor and resolves its plugin roots")


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-codex-agent: {failure}", file=sys.stderr)
        sys.exit(1)
