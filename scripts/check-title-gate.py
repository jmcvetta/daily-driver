#!/usr/bin/env python3
"""The acceptance test for the hook that holds the claim until the session is titled.

A gate is the worst place to break the rule *code without tests is broken*: it
sits in two lines of `hooks.json` that nothing else reads, on events nobody
watches, and its failure modes are opposite and both silent. A matcher that is
too narrow gives the claim back and the step is skipped again. A matcher that is
too wide denies every GitHub write. So the hook is run here exactly as the
harness runs it — the real script, synthetic event JSON on stdin — and the
answer is asserted on.

No model is needed, so it belongs in `make check` and in a CI that holds no
credentials. There is no live half: a denial is enforced by the harness.

No third-party imports: this runs from a Makefile on a laptop and from CI.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SCRIPT = ROOT / "hooks" / "title-gate.py"
SESSION_TITLE = ROOT / "skills" / "session-title" / "SKILL.md"

# `session-title`'s two forms, as that skill writes them. The gate's reason must
# quote both, and the skill must still say them this way: a change to either
# turns this red rather than silently splitting the gate from the skill.
ISSUE_FORM = "#{number} {shortened issue title}"
EPIC_FORM = "⛵ EPIC #{number} {shortened epic title}"

# Example titles in each form, and one that is not. The harness generates a title
# from the first prompt; it is not on purpose and does not count.
ISSUE_TITLE = "#52 Rotate the Aurora access token"
EPIC_TITLE = "⛵ EPIC #12 Rotate the tokens"
GENERATED_TITLE = "Agent session title bug"

# The calls the gate holds and the calls that put a title on record, under both
# server prefixes the harness has offered.
GATED = (
    "mcp__github__add_issue_comment",
    "mcp__claude-code-remote__create_session",
    "mcp__Claude_Code_Remote__create_session",
)
WATCHED = (
    "mcp__claude-code-remote__set_session_title",
    "mcp__claude-code-remote__get_session",
    "mcp__Claude_Code_Remote__set_session_title",
)

# Tool names the matchers must leave alone. A matcher written without anchors
# matches the lookalikes, and an empty one matches every tool.
NOT_GATED = (
    "mcp__github__issue_write",
    "mcp__github__issue_read",
    "mcp__github__add_comment_to_pending_review",
    "mcp__github__add_issue_comment_later",
    "mcp__github__update_pull_request",
    "Bash",
    "Edit",
    "Agent",
    "Task",
)
NOT_WATCHED = (
    "mcp__github__issue_read",
    "mcp__github__get_session_later",
    "mcp__claude-code-remote__list_sessions",
    "Bash",
    "Edit",
    "Agent",
)

# What the denial reason must keep saying. Prose in the script is free to
# change; these are what the change has to keep: that a retry buys nothing, the
# two calls that set the title, the two forms, who owns the budget, and that the
# denied call succeeds afterwards.
REQUIRED_IN_REASON = (
    "do not retry",
    "get_session",
    "set_session_title",
    ISSUE_FORM,
    EPIC_FORM,
    "session-title",
    "succeeds",
)


class Failed(Exception):
    """A check that did not hold. The message is the report."""


def spawn(
    mode: str | None, stdin: str, remote: bool = True, tmp: str | None = None
) -> subprocess.CompletedProcess[str]:
    """Run the hook script as the harness runs it: argv, stdin, and nothing else.

    `CLAUDE_PLUGIN_ROOT` is stripped deliberately: the harness sets it, the
    script must not need it. `CLAUDE_CODE_REMOTE` is set or removed as the case
    asks, and the temp directory is redirected so no case writes outside its own.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_CODE_REMOTE")
    }
    if remote:
        env["CLAUDE_CODE_REMOTE"] = "true"
    if tmp is not None:
        env["TMPDIR"] = tmp
    try:
        return subprocess.run(
            [str(SCRIPT), *([mode] if mode else [])],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
        )
    except OSError as error:
        raise Failed(
            f"{SCRIPT} could not be executed ({error.strerror or error}); the "
            f"hook command runs it directly"
        ) from None


def answer(
    errors: list[str],
    where: str,
    mode: str,
    event: dict | str,
    remote: bool = True,
    tmp: str | None = None,
) -> dict | None:
    """Invoke the hook and insist on a usable answer, or report and return None."""
    stdin = event if isinstance(event, str) else json.dumps(event)
    result = spawn(mode, stdin, remote=remote, tmp=tmp)
    if result.returncode != 0:
        errors.append(
            f"{where}: exited {result.returncode}; the decision rides on "
            f"stdout, which a nonzero exit puts at risk\n  stderr: "
            f"{result.stderr.strip() or '(empty)'}"
        )
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        errors.append(f"{where}: stdout is not JSON ({error}): {result.stdout[:200]!r}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{where}: emitted {type(payload).__name__}, not an object")
        return None
    return payload


def decision(payload: dict) -> str | None:
    output = payload.get("hookSpecificOutput")
    return output.get("permissionDecision") if isinstance(output, dict) else None


def pre_event(tool: str, session: str, scratch: str | None) -> dict:
    event = {
        "session_id": session,
        "cwd": str(ROOT),
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {"issue_number": 52, "body": "Claiming."},
        "tool_use_id": "toolu_check",
    }
    if scratch is not None:
        event["scratchpad_dir"] = scratch
    return event


def post_event(
    tool: str,
    session: str,
    scratch: str | None,
    tool_input: dict,
    tool_response: object,
) -> dict:
    event = {
        "session_id": session,
        "cwd": str(ROOT),
        "hook_event_name": "PostToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
        "tool_response": tool_response,
        "tool_use_id": "toolu_check",
    }
    if scratch is not None:
        event["scratchpad_dir"] = scratch
    return event


def get_session_response(title: str) -> dict:
    """What `get_session` answers: JSON text in an MCP content block."""
    text = json.dumps({"ccr": {"id": "session_check", "title": title}})
    return {"content": [{"type": "text", "text": text}]}


def check_wiring(errors: list[str]) -> None:
    """hooks.json runs this script in both modes, on the calls it should and no others."""
    if not os.access(SCRIPT, os.X_OK):
        errors.append(
            f"{SCRIPT.relative_to(ROOT)} is not executable; the hook command "
            f"runs it directly, so the bit is load-bearing"
        )
    try:
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8")).get("hooks", {})
    except (OSError, json.JSONDecodeError) as error:
        raise Failed(f"hooks/hooks.json: {error}") from None

    for event, mode, should, should_not in (
        ("PreToolUse", "pre-tool-use", GATED, NOT_GATED),
        ("PostToolUse", "post-tool-use", WATCHED, NOT_WATCHED),
    ):
        entries = [
            (entry, handler)
            for entry in config.get(event, [])
            for handler in entry.get("hooks", [])
            if SCRIPT.name in handler.get("command", "")
        ]
        if len(entries) != 1:
            errors.append(
                f"hooks/hooks.json: {event} has {len(entries)} handlers running "
                f"{SCRIPT.name}, expected exactly 1"
            )
            continue
        entry, handler = entries[0]
        command = handler.get("command", "")
        if "${CLAUDE_PLUGIN_ROOT}" not in command:
            errors.append(
                f"hooks/hooks.json: {command!r} does not resolve the script "
                f"through ${{CLAUDE_PLUGIN_ROOT}}"
            )
        if not command.rstrip().endswith(mode):
            errors.append(
                f"hooks/hooks.json: the {event} command {command!r} does not "
                f"pass the mode {mode!r}"
            )
        matcher = entry.get("matcher", "")
        if not matcher:
            errors.append(
                f"hooks/hooks.json: the {event} entry running {SCRIPT.name} has "
                f"no matcher, and Claude Code reads that as every tool"
            )
            continue
        try:
            re.compile(matcher)
        except re.error as error:
            raise Failed(
                f"hooks/hooks.json: {event} matcher {matcher!r} is not a regular "
                f"expression ({error})"
            ) from None
        for tool in should:
            if not re.search(matcher, tool):
                errors.append(
                    f"hooks/hooks.json: {event} matcher {matcher!r} does not "
                    f"match {tool!r}"
                )
        for tool in should_not:
            if re.search(matcher, tool):
                errors.append(
                    f"hooks/hooks.json: {event} matcher {matcher!r} also matches "
                    f"{tool!r}, which this hook has no business touching"
                )


def check_forms(errors: list[str]) -> None:
    """The forms the gate quotes are still the forms `session-title` states."""
    try:
        text = SESSION_TITLE.read_text(encoding="utf-8")
    except OSError as error:
        raise Failed(f"{SESSION_TITLE.relative_to(ROOT)}: {error}") from None
    for form in (ISSUE_FORM, EPIC_FORM):
        if form not in text:
            errors.append(
                f"{SESSION_TITLE.relative_to(ROOT)} no longer states the form "
                f"{form!r}; the gate's reason and regexes quote it"
            )


def check_cases(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as scratch, tempfile.TemporaryDirectory() as tmp:

        def denied(where: str, tool: str, session: str, scratch_dir=scratch) -> None:
            payload = answer(
                errors, where, "pre-tool-use", pre_event(tool, session, scratch_dir),
                tmp=tmp,
            )
            if payload is None:
                return
            if decision(payload) != "deny":
                errors.append(
                    f"{where}: permissionDecision is {decision(payload)!r}, not 'deny'"
                )
                return
            reason = payload["hookSpecificOutput"].get("permissionDecisionReason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{where}: the denial carries no reason")
                return
            for needle in REQUIRED_IN_REASON:
                if needle not in reason.lower() and needle not in reason:
                    errors.append(f"{where}: the denial reason never says {needle!r}")

        def allowed(
            where: str, tool: str, session: str, scratch_dir=scratch, remote=True
        ) -> None:
            payload = answer(
                errors, where, "pre-tool-use", pre_event(tool, session, scratch_dir),
                remote=remote, tmp=tmp,
            )
            if payload is not None and decision(payload) is not None:
                errors.append(
                    f"{where}: permissionDecision is {decision(payload)!r}; the "
                    f"call should have been allowed"
                )

        def record(where: str, event: dict) -> None:
            answer(errors, where, "post-tool-use", event, tmp=tmp)

        # Denied with no record; and `create_session` behaves the same.
        denied("a comment before any title", GATED[0], "s-none")
        denied("a dispatch before any title", GATED[1], "s-none")
        denied("a dispatch under the other server prefix", GATED[2], "s-none")

        # `set_session_title` puts a title on record, whatever the title.
        record(
            "set_session_title",
            post_event(
                WATCHED[0], "s-set", scratch, {"session_id": "s-set", "title": ISSUE_TITLE}, {}
            ),
        )
        allowed("a comment after set_session_title", GATED[0], "s-set")
        allowed("a dispatch after set_session_title", GATED[1], "s-set")

        # `get_session` reporting a title in either form is a title set on purpose:
        # what lets an `embark` session created with a title claim unrenamed.
        for label, title in (("issue", ISSUE_TITLE), ("epic", EPIC_TITLE)):
            session = f"s-get-{label}"
            record(
                f"get_session reporting the {label} form",
                post_event(WATCHED[1], session, scratch, {}, get_session_response(title)),
            )
            allowed(f"a comment after get_session reported {title!r}", GATED[0], session)

        # A harness-generated title does not count, and neither does a
        # `get_session` about some other session.
        record(
            "get_session reporting the generated title",
            post_event(
                WATCHED[1], "s-generated", scratch, {}, get_session_response(GENERATED_TITLE)
            ),
        )
        denied("a comment after get_session reported a generated title", GATED[0], "s-generated")
        record(
            "get_session on another session",
            post_event(
                WATCHED[1], "s-other", scratch, {"session_id": "session_x"},
                get_session_response(ISSUE_TITLE),
            ),
        )
        denied("a comment after get_session on another session", GATED[0], "s-other")

        # Every shape a response arrives in is read, and an unreadable one
        # records nothing and says so.
        record(
            "get_session answered as bare text",
            post_event(
                WATCHED[1], "s-text", scratch, {},
                json.dumps({"ccr": {"title": ISSUE_TITLE}}),
            ),
        )
        allowed("a comment after a bare-text get_session answer", GATED[0], "s-text")
        result = spawn(
            "post-tool-use",
            json.dumps(post_event(WATCHED[1], "s-junk", scratch, {}, "not json")),
            tmp=tmp,
        )
        if result.returncode != 0 or "title-gate:" not in result.stderr:
            errors.append(
                "a get_session answer that cannot be parsed must exit 0 and say "
                f"so on stderr (exit {result.returncode}, stderr {result.stderr!r})"
            )
        denied("a comment after an unparseable get_session answer", GATED[0], "s-junk")

        # Two sessions do not share a record.
        denied("a second session beside a titled one", GATED[0], "s-second")

        # With no scratchpad the record falls back to the temp directory, and
        # is still keyed by session.
        record(
            "set_session_title with no scratchpad_dir",
            post_event(WATCHED[0], "s-tmp", None, {"title": ISSUE_TITLE}, {}),
        )
        allowed("a comment on the temp-directory record", GATED[0], "s-tmp", scratch_dir=None)
        denied("another session on the temp-directory record", GATED[0], "s-tmp-2", scratch_dir=None)
        if not (Path(tmp) / "daily-driver" / "s-tmp").is_dir():
            errors.append(
                "with no scratchpad_dir the record is expected under "
                "<tmp>/daily-driver/<session_id>/"
            )

        # A laptop session has no title surface: nothing is denied.
        allowed("a comment with CLAUDE_CODE_REMOTE unset", GATED[0], "s-none", remote=False)
        allowed("a dispatch with CLAUDE_CODE_REMOTE unset", GATED[1], "s-none", remote=False)

        # The one case that fails open: an event naming another tool means the
        # matcher is wrong, and the hook must say so rather than decide for it.
        payload = answer(
            errors, "an event naming Bash", "pre-tool-use",
            dict(pre_event("Bash", "s-none", scratch), tool_input={"command": "ls"}),
            tmp=tmp,
        )
        if payload is not None:
            if decision(payload) is not None:
                errors.append("an event naming Bash was decided for; a wrong matcher must not deny")
            if SCRIPT.stem not in (payload.get("systemMessage") or ""):
                errors.append(
                    "an event naming Bash carries no systemMessage naming the "
                    "hook, so a wrong matcher would never be noticed"
                )

        # An event the hook cannot read is still the gated call: the matcher
        # already identified it, so it is denied.
        for stdin in ("", "not json at all", "[]", "null", "{}"):
            payload = answer(errors, f"unusable stdin {stdin!r}", "pre-tool-use", stdin, tmp=tmp)
            if payload is not None and decision(payload) != "deny":
                errors.append(f"unusable stdin {stdin!r} was not denied")


def check_bad_argv(errors: list[str]) -> None:
    """A typo in hooks.json exits nonzero rather than passing silently."""
    for mode in (None, "session-start"):
        result = spawn(mode, "{}")
        if result.returncode == 0:
            errors.append(f"mode {mode!r} exited 0; a typo in hooks.json would be silent")


def main() -> int:
    errors: list[str] = []
    try:
        check_wiring(errors)
        check_forms(errors)
        check_cases(errors)
        check_bad_argv(errors)
    except Failed as failure:
        errors.append(str(failure))

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(
        f"the title is gated: {SCRIPT.relative_to(ROOT)} denies the first issue "
        f"comment and the first dispatch until the session is titled"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
