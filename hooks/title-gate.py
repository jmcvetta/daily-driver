#!/usr/bin/env python3
"""Hold the session's first issue comment and first dispatch until it is titled.

`undertake` and `embark` both carry a `Title the session` step, and agents on
Claude Code skip it. Prose fixes did not hold: nothing fails when the step is
dropped, so a session that drops it is never told. A rule with no mid-task
judgement in it is enforced, not instructed — the argument
`docs/notes/0009-deny-the-question-widget.md` makes for the question widget —
and this hook is that argument applied to the title. The decision is
`docs/notes/0032-the-title-is-gated-not-instructed.md`.

Two modes, one script, in the shape of `inject-constitution.py`:

- `post-tool-use` watches the two calls that put a title on record:
  `set_session_title`, and `get_session` where its answer already carries a
  title in one of the two forms `session-title` defines. It writes the record.
- `pre-tool-use` guards the two calls the title must precede: a comment on an
  issue or pull request, and the dispatch of a session. It denies either until
  the record exists, and the denial carries everything a denied session needs.

The gate checks that a title was set, and where it can read the current title
it checks the form. It never checks the budget or the wording: those stay
`session-title`'s. It only gates where `CLAUDE_CODE_REMOTE` is set. A laptop
session has no title surface, and `session-title`'s `Setting it` says to stop
at the step there, not at the claim.

The record is a small file keyed by the event's `session_id`, under the event's
`scratchpad_dir` when present and otherwise under the system temp directory.
Not the transcript: Claude Code writes it asynchronously, so it lags the turn
and is no source of truth for a hook. A subagent shares its parent's
`session_id`, so it shares the record.

Usage: title-gate.py {pre-tool-use,post-tool-use}

The event JSON arrives on stdin and the hook's answer goes to stdout. See
`hooks/hooks.json` for the wiring, and `scripts/check-title-gate.py` for the
acceptance test.

No third-party imports. This runs on a laptop, on a web worker, and out of a
test harness; a dependency install between those is a place for them to differ.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
from pathlib import Path

MODES = {
    "pre-tool-use": "PreToolUse",
    "post-tool-use": "PostToolUse",
}

# The calls each mode is wired to. The matchers in `hooks.json` select the
# call; these names only notice that a matcher has gone wrong. The server
# prefix is whatever the session registers (`mcp__claude-code-remote__…` and
# `mcp__Claude_Code_Remote__…` have both been offered), so only the operation
# name is read.
GATED = ("add_issue_comment", "create_session")
WATCHED = ("set_session_title", "get_session")

# `session-title`'s two forms, as patterns. They are a second copy of that
# skill's forms, so `scripts/check-title-gate.py` asserts on both by example
# and against the skill's own text: a form change turns the repository red
# here instead of silently splitting.
FORMS = (
    re.compile(r"^#\d+ \S"),
    re.compile(r"^⛵ EPIC #\d+ \S"),
)

# What the session is told when the call is denied. Claude Code shows this text
# and nothing else, so it is written to be acted on rather than read.
REASON = (
    "This tool is shut until the session is titled. A retry is denied the "
    "same way, so do not retry it.\n\n"
    "Set the title first, with two calls on the Claude Code Remote server: "
    "`get_session` with `session_id` omitted answers this session's own id, "
    "then `set_session_title` with that `session_id` and the title. The "
    "server prefix is whatever the session registers, so judge the tool by "
    "its operation name.\n\n"
    "The title takes one of two forms:\n\n"
    "    #{number} {shortened issue title}\n"
    "    ⛵ EPIC #{number} {shortened epic title}\n\n"
    "The first is for a session working on an issue. The second is for the "
    "session an epic is run from. The `session-title` skill owns the budget "
    "and the shortening.\n\n"
    "Once the title is set, the call you were denied succeeds."
)


def title_of(text: object) -> str | None:
    """The `ccr.title` of a `get_session` answer, or None where there is none."""
    try:
        answer = json.loads(text) if isinstance(text, str) else text
    except json.JSONDecodeError:
        return None
    if not isinstance(answer, dict):
        return None
    ccr = answer.get("ccr")
    title = ccr.get("title") if isinstance(ccr, dict) else None
    return title if isinstance(title, str) else None


def response_text(response: object) -> str | None:
    """The text a tool response carries, from any of the shapes MCP uses.

    A tool response arrives as bare text, as a list of content blocks, or as an
    object holding that list. The hook reads the text and nothing else.
    """
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        if "content" in response:
            return response_text(response["content"])
        text = response.get("text")
        return text if isinstance(text, str) else None
    if isinstance(response, list):
        parts = [
            part
            for part in (response_text(item) for item in response)
            if part is not None
        ]
        return "\n".join(parts) if parts else None
    return None


def in_form(title: str) -> bool:
    return any(form.search(title) for form in FORMS)


def record_path(event: dict) -> Path:
    """Where this session's record lives."""
    session = event.get("session_id")
    key = re.sub(r"[^A-Za-z0-9_.-]", "_", session) if isinstance(session, str) else ""
    key = key or "no-session"
    scratch = event.get("scratchpad_dir")
    if isinstance(scratch, str) and scratch:
        return Path(scratch) / f"title-gate-{key}.json"
    return Path(tempfile.gettempdir()) / "daily-driver" / key / "title-gate.json"


def is_recorded(event: dict) -> bool:
    return record_path(event).is_file()


def write_record(event: dict, title: str, how: str) -> None:
    path = record_path(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"title": title, "how": how}), encoding="utf-8")


def operation(tool: object) -> str:
    """The operation name of an MCP tool, `mcp__<server>__<operation>`."""
    return tool.rsplit("__", 1)[-1] if isinstance(tool, str) else ""


def decide_post(event: dict) -> tuple[dict, str | None]:
    """Record a title where the call put one on record."""
    payload: dict = {}
    tool = event.get("tool_name")
    op = operation(tool)
    if op not in WATCHED:
        names = ", ".join(repr(name) for name in WATCHED)
        note = (
            f"title-gate was invoked on {tool!r}, which is neither of {names}, "
            f"so nothing was recorded. The PostToolUse matcher in "
            f"hooks/hooks.json is wrong."
        )
        return payload, note

    tool_input = event.get("tool_input")
    if not isinstance(tool_input, dict):
        tool_input = {}

    if op == "set_session_title":
        title = tool_input.get("title")
        if isinstance(title, str) and title.strip():
            write_record(event, title, "set_session_title")
        return payload, None

    # `get_session` with a `session_id` describes another session, not this one.
    if tool_input.get("session_id"):
        return payload, None
    text = response_text(event.get("tool_response"))
    title = title_of(text)
    if title is None:
        return payload, "get_session answered no readable ccr.title; nothing recorded"
    if in_form(title):
        write_record(event, title, "get_session")
    return payload, None


def decide_pre(event: dict) -> tuple[dict, str | None]:
    """Deny the gated call until the session is titled.

    The rule is: deny unless the event positively names some other tool, or the
    session is not on the surface that has a title, or the record exists. The
    matcher in `hooks.json` is what identifies the call, so an event this
    script cannot read does not overturn it. An event that names some *other*
    tool is let through: that means the matcher is wrong, and denying an
    unrelated tool on a broken matcher is the worse failure.
    """
    allow: dict = {"hookSpecificOutput": {"hookEventName": "PreToolUse"}}
    tool = event.get("tool_name")
    if isinstance(tool, str) and operation(tool) not in GATED:
        names = ", ".join(repr(name) for name in GATED)
        note = (
            f"title-gate was invoked on {tool!r}, which is neither of {names}, "
            f"so the call was allowed. The PreToolUse matcher in "
            f"hooks/hooks.json is wrong."
        )
        return allow, note

    if not os.environ.get("CLAUDE_CODE_REMOTE"):
        return allow, None
    if is_recorded(event):
        return allow, None

    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }, None


def emit(payload: dict, note: str | None) -> int:
    """Write the hook's answer, and be loud about a misfire without being fatal.

    Exit 0 on both paths. A nonzero exit risks the harness discarding the
    stdout that carries the decision.
    """
    if note is not None:
        payload["systemMessage"] = f"daily-driver: {note}"
        print(f"title-gate: {note}", file=sys.stderr)

    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


def read_event() -> dict:
    """The event on stdin, or an empty one where it cannot be read."""
    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        print(f"title-gate: unparseable event JSON: {error}", file=sys.stderr)
        return {}

    if not isinstance(event, dict):
        print(
            f"title-gate: event JSON is {type(event).__name__}, not an object",
            file=sys.stderr,
        )
        return {}

    return event


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in MODES:
        # A typo in hooks.json lands here. Exit 2 is the loud answer, and on
        # PreToolUse it blocks the call anyway, so a misconfigured hook fails
        # towards the behaviour it was installed for rather than away from it.
        print(
            f"usage: {argv[0].rsplit('/', 1)[-1]} {{{','.join(MODES)}}}",
            file=sys.stderr,
        )
        return 2

    event = read_event()
    decide = decide_pre if argv[1] == "pre-tool-use" else decide_post
    return emit(*decide(event))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
