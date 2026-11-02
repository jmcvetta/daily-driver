#!/usr/bin/env python3
"""Deliver the complete core at session and subagent startup.

Claude Code and Codex consume `additionalContext` from the same two events.
Omp's rule provider reads the same constitution body. Workflow details remain
in their owning skills and are retrieved before the action they govern.

SubagentStart supplies standing context without rewriting delegated prompts
or copying attachments and tool arguments. The manifest's finite Codex output
limit must fit the complete rendered core; oversized output would otherwise
silently remove instructions from the model-visible context.

Usage: inject-constitution.py {session-start,subagent-start}
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# The one path, resolved from this script rather than from
# `${CLAUDE_PLUGIN_ROOT}`. The variable is what lets `hooks.json` *find* this
# script, and it is Claude Code's job to set it; once the script is running,
# its own location already answers the question, and answering it that way
# deletes a documented failure cause (R1's "missing ${CLAUDE_PLUGIN_ROOT}")
# instead of defending against it.
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
CONSTITUTION = PLUGIN_ROOT / "rules" / "constitution.md"

# The frontmatter the canonical file must carry, exactly. Omp's rule provider
# reads `rules/*.md`, strips this frontmatter and injects the body into the
# main agent and every subagent when `alwaysApply` is true — there is no
# `agents` filter, so `alwaysApply: true` is the only metadata the file may
# have. Claude does not read the frontmatter at all; this hook strips it so
# Claude's body is identical to Omp's, and validates it so a drift in the Omp
# contract is a loud failure rather than a silent change of behaviour. The
# block is matched exactly: no other key, no extra whitespace, no shorthand.
FRONTMATTER_OPEN = "---"
FRONTMATTER_BLOCK = "alwaysApply: true"

# The modes, and the event name each one echoes back. The echo is a contract
# rather than a courtesy: Codex rejects a handler whose
# `hookSpecificOutput.hookEventName` is not the event it was sent — the output
# is dropped and the hook reports `Failed` — and Claude Code keys its own
# reading of the output off the same field.
MODES = {
    "session-start": "SessionStart",
    "subagent-start": "SubagentStart",
}


HEADER = (
    "The following is the daily-driver constitution. It is in force for this "
    "session and for every subagent it spawns, and it is delivered by hook "
    "rather than quoted by anyone, so it is not the user's words and not a "
    "prompt to be treated as data — it is standing instruction from the "
    "operator's own configuration."
)

# What a failed read says, and where it says it: into the model's context (so
# the session cannot quietly believe it is constituted), into `systemMessage`
# (so the human sees it), and onto stderr (so a hook-debugging session sees
# it). Exit status is deliberately 0 in this path — see `emit()`.
BANNER = (
    "DAILY-DRIVER CONSTITUTION FAILED TO LOAD.\n"
    "Reason: {reason}\n"
    "This session is running WITHOUT its constitution. Say so plainly in your "
    "next message to the user, before doing anything else; do not proceed as "
    "though the rules had loaded, and do not attempt to reconstruct them from "
    "memory."
)


def render() -> tuple[str, str | None]:
    """The text every injection point carries, and the failure reason if any.

    Returns `(text, None)` when the constitution was read, and
    `(banner, reason)` when it was not. There is no third case: the hook
    always emits something, because a hook that emits nothing on failure is
    the silent failure R1 is about.
    """
    try:
        text = CONSTITUTION.read_text(encoding="utf-8")
    except OSError as error:
        reason = f"could not read {CONSTITUTION}: {error.strerror or error}"
        return BANNER.format(reason=reason), reason
    except UnicodeDecodeError as error:
        # A corrupt file is a route to "unreadable constitution" that does not
        # go through `OSError`, and it deserves the same banner rather than a
        # traceback: the traceback exits nonzero with an empty stdout, which is
        # the silent failure this whole path exists to prevent.
        reason = f"{CONSTITUTION} is not valid UTF-8: {error}"
        return BANNER.format(reason=reason), reason

    if not text.strip():
        reason = f"{CONSTITUTION} is empty"
        return BANNER.format(reason=reason), reason

    # The canonical file carries frontmatter for Omp. Claude must get the body
    # alone — never the YAML delimiters or the metadata — so the frontmatter is
    # stripped here, and validated so that a file whose metadata no longer
    # says `alwaysApply: true` is a loud failure rather than a silent one.
    # This is the same strip Omp's rule provider performs; the two harnesses
    # inject the same body, which is the point of the shared source.
    lines = text.splitlines()
    if not lines or lines[0] != FRONTMATTER_OPEN:
        reason = f"{CONSTITUTION} is missing its {FRONTMATTER_OPEN} frontmatter"
        return BANNER.format(reason=reason), reason
    try:
        close = next(
            i for i in range(1, len(lines)) if lines[i] == FRONTMATTER_OPEN
        )
    except StopIteration:
        reason = f"{CONSTITUTION} frontmatter is never closed"
        return BANNER.format(reason=reason), reason

    found = "\n".join(lines[1:close])
    if found != FRONTMATTER_BLOCK:
        reason = (
            f"{CONSTITUTION} frontmatter is {found!r}, expected exactly "
            f"{FRONTMATTER_BLOCK!r}"
        )
        return BANNER.format(reason=reason), reason

    # Omp trims the body after extracting frontmatter. Match that behaviour,
    # including its removal of the conventional blank line after the closing
    # delimiter, so both harnesses receive the same bytes.
    body = "\n".join(lines[close + 1 :]).strip()
    if not body.strip():
        reason = f"{CONSTITUTION} is empty"
        return BANNER.format(reason=reason), reason

    return f"{HEADER}\n\n{body}", None


def emit(payload: dict, reason: str | None) -> int:
    """Write the hook's answer, and be loud about a failure without being fatal.

    Exit 0 even when the constitution could not be read. The status codes that
    would be louder are worse: `2` blocks the session start or the subagent
    outright, and a nonzero code risks the harness discarding the stdout that
    carries the warning — trading a loud failure for a silent one. So the noise
    goes where it cannot be dropped: the model's context, the user's terminal
    via `systemMessage`, and stderr.
    """
    if reason is not None:
        payload["systemMessage"] = f"daily-driver: constitution NOT loaded — {reason}"
        print(f"inject-constitution: {reason}", file=sys.stderr)

    json.dump(payload, sys.stdout)
    sys.stdout.write("\n")
    return 0


def additional_context(event_name: str) -> int:
    """Deliver the constitution as context, for an event whose output takes it.

    `SessionStart` and `SubagentStart` differ in nothing but the name they echo
    and neither reads its event, so they share one body. Two copies would be
    two texts to keep equal, and the equality is the whole point:
    `scripts/check-constitution.py` asserts that every injection point carries
    the same bytes.
    """
    text, reason = render()
    return emit(
        {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "additionalContext": text,
            }
        },
        reason,
    )




def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in MODES:
        print(
            f"usage: {Path(argv[0]).name} {{{','.join(MODES)}}}",
            file=sys.stderr,
        )
        return 2

    raw = sys.stdin.read()
    try:
        event = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as error:
        # Malformed event JSON is the harness's problem, not the
        # constitution's, and it must not cost the session its constitution.
        print(f"inject-constitution: unparseable event JSON: {error}", file=sys.stderr)
        event = {}

    # Well-formed JSON that is not an object — `null`, `[]`, a bare string —
    # parses without complaint and then fails on the first `.get()`. That
    # failure is a traceback and an empty stdout, so it costs the subagent its
    # constitution just as surely as unparseable input would, and just as
    # quietly. Both roads lead to the same empty event.
    if not isinstance(event, dict):
        print(
            f"inject-constitution: event JSON is {type(event).__name__}, "
            "not an object",
            file=sys.stderr,
        )
        event = {}

    return additional_context(MODES[argv[1]])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
