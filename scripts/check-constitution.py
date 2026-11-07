#!/usr/bin/env python3
"""Reject missing, duplicated, truncated, or prompt-rewriting core delivery.

The shipped hooks run against offline event fixtures in the existing suite.
Installed-runtime proofs separately observe whether each harness delivers the
context. Neither fixture type proves model compliance.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SCRIPT = ROOT / "hooks" / "inject-constitution.py"
CONSTITUTION = ROOT / "rules" / "constitution.md"

# The frontmatter the canonical file must carry so Omp injects it everywhere.
# Omp's rule provider reads `rules/*.md`, strips the frontmatter and — because
# there is no `agents` filter — injects the body into the main agent and every
# subagent when `alwaysApply` is true. That is the Omp half of "one canonical
# source, two harnesses": the body Omp injects must be identical to the body
# this hook injects for Claude, which is why the exact block is asserted here.
CONSTITUTION_FRONTMATTER = "alwaysApply: true"



def constitution_body() -> str:
    """The constitution without its Omp frontmatter, as both harnesses inject it.

    Mirrors the strip in `hooks/inject-constitution.py` and, for `alwaysApply`
    files, in Omp's own rule provider: the YAML delimiters and everything
    between them come off, leaving the body both harnesses deliver. This is
    what the byte-equality between the two injection points is asserted on, so
    the frontmatter cannot silently leak into a session.
    """
    text = CONSTITUTION.read_text(encoding="utf-8")
    return _strip_frontmatter(text)


def _strip_frontmatter(text: str) -> str:
    """Remove a leading `---`-delimited frontmatter block, like Omp's provider."""
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return text
    for i in range(1, len(lines)):
        if lines[i] == "---":
            # Omp's parser trims the body after extracting the frontmatter.
            return "\n".join(lines[i + 1 :]).strip()
    return text


SESSION_START_EVENT = {
    "session_id": "check-constitution",
    "cwd": str(ROOT),
    "hook_event_name": "SessionStart",
    "startup_reason": "startup",
}

# Startup context must not depend on a delegated prompt or its attachments.
SUBAGENT_START_EVENT = {
    "session_id": "check-constitution",
    "cwd": str(ROOT),
    "hook_event_name": "SubagentStart",
    "agent_id": "agent_check",
    "agent_type": "Explore",
}


def codex(hook_event_name: str, **event: object) -> dict:
    """A Codex-shaped hook event: its envelope, then this event's own keys.

    The envelope is the stdin measured in issue #181 — `transcript_path`,
    `model` and `permission_mode` beside the common `session_id`, `cwd` and
    `hook_event_name`. Built here rather than derived from the Claude Code
    events above, because a Codex event carrying a Claude Code key would be a
    fixture claiming to be measured and not being one.
    """
    return {
        "session_id": "01a0962d-check-constitution",
        "transcript_path": str(ROOT / "rollout-check.jsonl"),
        "cwd": str(ROOT),
        "model": "stub-model",
        "permission_mode": "bypassPermissions",
        "hook_event_name": hook_event_name,
        **event,
    }


# Native Codex startup and delegation use the same context-only contract.
CODEX_SESSION_START_EVENT = codex("SessionStart", source="startup")
CODEX_SUBAGENT_START_EVENT = codex("SubagentStart")

# Every event that carries the constitution as context, and the mode that
# answers it. Both harnesses, because a route that stops reaching one of them
# does not fail — it silently delivers nothing on that harness alone.
CONTEXT_EVENTS = (
    ("Claude Code", "session-start", "SessionStart", SESSION_START_EVENT),
    ("Claude Code", "subagent-start", "SubagentStart", SUBAGENT_START_EVENT),
    ("Codex", "session-start", "SessionStart", CODEX_SESSION_START_EVENT),
    ("Codex", "subagent-start", "SubagentStart", CODEX_SUBAGENT_START_EVENT),
)



class Failed(Exception):
    """A check that did not hold. The message is the report."""


def spawn(script: Path, mode: str, stdin: str) -> subprocess.CompletedProcess[str]:
    """Run a hook script as the harness runs it: argv, stdin, and nothing else.

    `CLAUDE_PLUGIN_ROOT` is stripped deliberately. The harness sets it, the
    script must not need it, and clearing it here is the regression test for
    that -- see PLUGIN_ROOT in the script.
    """
    try:
        return subprocess.run(
            [str(script), mode],
            input=stdin,
            capture_output=True,
            text=True,
            cwd=ROOT,
            env={k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"},
        )
    except OSError as error:
        raise Failed(
            f"{script} {mode} could not be executed ({error.strerror or error}); "
            f"the hook command runs it directly"
        ) from None


def run_hook(mode: str, event: dict) -> dict:
    """Invoke a hook the way Claude Code does, and insist on a usable answer."""
    where = f"hooks/inject-constitution.py {mode}"
    result = spawn(SCRIPT, mode, json.dumps(event))
    if result.returncode != 0:
        raise Failed(
            f"{where}: exited {result.returncode}; a nonzero exit is a session "
            f"with no constitution and no reliable warning\n  stderr: "
            f"{result.stderr.strip() or '(empty)'}"
        )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise Failed(
            f"{where}: stdout is not JSON ({error}); the harness would ignore "
            f"it\n  stdout: {result.stdout[:200]!r}"
        ) from None
    if not isinstance(payload, dict):
        raise Failed(f"{where}: emitted {type(payload).__name__}, not an object")
    return payload


def hook_specific(payload: dict, event_name: str, where: str) -> dict:
    output = payload.get("hookSpecificOutput")
    if not isinstance(output, dict):
        raise Failed(f"{where}: no hookSpecificOutput object")
    if output.get("hookEventName") != event_name:
        raise Failed(
            f"{where}: hookEventName is {output.get('hookEventName')!r}, "
            f"expected {event_name!r} -- Claude Code keys the output off this"
        )
    return output


def own_handlers(config: dict, event: str) -> list[tuple[dict, dict]]:
    """The entries and handlers for `event` that run the constitution script.

    The plugin wires more than one hook to `PreToolUse` — `hooks/ask-in-chat.py`
    is on the same event, matched on a different tool — so every assertion
    below has to say which handler it is about. Scoping by the command that
    names this script is what keeps a second hook from reading as a second
    constitution, or its matcher as one of ours.
    """
    return [
        (entry, handler)
        for entry in config.get(event) or []
        for handler in entry.get("hooks", [])
        if SCRIPT.name in handler.get("command", "")
    ]


def check_wiring(errors: list[str]) -> None:
    """Prevent duplicate injections and Codex's default hook-output truncation."""
    try:
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8")).get("hooks", {})
    except (OSError, json.JSONDecodeError) as error:
        raise Failed(f"hooks/hooks.json: {error}") from None
    commands: dict[str, str] = {}

    for event, expected_mode in (
        ("SessionStart", "session-start"),
        ("SubagentStart", "subagent-start"),
    ):
        handlers = [h for _, h in own_handlers(config, event)]
        if len(handlers) != 1:
            errors.append(
                f"hooks/hooks.json: {event} has {len(handlers)} handlers "
                f"running {SCRIPT.name}, expected exactly 1"
            )
            continue
        command = handlers[0].get("command", "")
        commands[event] = command
        if not command.endswith(f" {expected_mode}"):
            errors.append(
                f"hooks/hooks.json: the {event} command does not end in "
                f"{expected_mode!r}: {command!r}"
            )
        if "*" in command or "glob" in command:
            errors.append(
                f"hooks/hooks.json: the {event} command looks like a glob "
                f"({command!r}); D12 is one file read by exact path"
            )
        limit = handlers[0].get("additionalContextLimit")
        if limit != 5000:
            errors.append(
                f"hooks/hooks.json: {event} needs its finite 5000-token cap "
                "to avoid truncated context"
            )

    # One script for every event is what makes "the same file, by exact path"
    # structural rather than aspirational: there is only one path constant.
    stems = {c.rsplit(" ", 1)[0] for c in commands.values()}
    if len(stems) > 1:
        errors.append(
            "hooks/hooks.json: the events run different commands "
            f"({sorted(stems)}); they must run the one script, so that they "
            "cannot read different files"
        )
    for command in stems:
        if SCRIPT.name not in command:
            errors.append(f"hooks/hooks.json: {command!r} does not name {SCRIPT.name}")
        if "${CLAUDE_PLUGIN_ROOT}" not in command:
            errors.append(
                f"hooks/hooks.json: {command!r} does not resolve the script "
                "through ${CLAUDE_PLUGIN_ROOT}; nothing else knows where an "
                "installed plugin lives"
            )

    if own_handlers(config, "PreToolUse"):
        errors.append(
            "hooks/hooks.json: core delivery must not rewrite delegated prompts "
            "or duplicate SubagentStart context through PreToolUse"
        )

    # `SubagentStart` is matched on the agent *type*, not on a tool name, so
    # any matcher there exempts every other kind of subagent from the
    # constitution — and exempts them silently, which is R1's failure mode
    # pointed at delegation. The entry must carry none.
    for entry, _ in own_handlers(config, "SubagentStart"):
        if entry.get("matcher"):
            errors.append(
                f"hooks/hooks.json: the SubagentStart entry has matcher "
                f"{entry['matcher']!r}; that field matches the agent type, so "
                f"a value there leaves every other kind of subagent "
                f"unconstituted"
            )

    if not os.access(SCRIPT, os.X_OK):
        errors.append(
            f"{SCRIPT.relative_to(ROOT)} is not executable; the hook command "
            "runs it directly, so the bit is load-bearing"
        )


def check_delivery(errors: list[str]) -> None:
    """Reject omitted, duplicated, or oversized bodies on any delivery route."""
    body = constitution_body()

    for harness, mode, event_name, event in CONTEXT_EVENTS:
        where = f"{event_name} on {harness}"
        output = hook_specific(run_hook(mode, event), event_name, where)
        context = output.get("additionalContext")
        if not isinstance(context, str) or not context.strip():
            errors.append(f"{where}: additionalContext is missing or empty")
            continue
        if not context.endswith(body) or context.count(body) != 1:
            errors.append(f"{where}: additionalContext must end with one complete core")
        if len(context.encode("utf-8")) > 9000:
            errors.append(f"{where}: rendered core exceeds the proved 9000-byte budget")
        if "updatedInput" in output:
            errors.append(f"{where}: startup context must not rewrite tool input")



def check_loud_failure(errors: list[str]) -> None:
    """A constitution that cannot be read says so, everywhere it can.

    R1's whole point: the interesting failure is not the hook that crashes, it
    is the hook that returns cleanly having delivered nothing. So this stands
    up a plugin root whose constitution cannot be used and insists on the
    noise. Ways it cannot be used, each leaving the script by its own door:
    absent (`OSError`), present but blank (no exception at
    all), present but not decodable (`UnicodeDecodeError`, which is a
    `ValueError` and so walks straight past a bare `except OSError`), and —
    since the file now carries Omp frontmatter the hook must strip — present
    with a frontmatter block that is missing, unclosed, or not exactly
    `alwaysApply: true`, all of which fail validation rather than vanish.
    """
    for label, content in (
        ("missing", None),
        ("empty", b"\n   \n"),
        ("non-UTF-8", b"# Constitution\n\xff\xfe not text\n"),
        ("no-frontmatter", b"# Constitution\n\nNo YAML block at all.\n"),
        ("unclosed-frontmatter", b"---\nalwaysApply: true\n# never closed\n"),
        ("bad-frontmatter", b"---\nalwaysApply: false\n---\n\nbody\n"),
        ("indented-open-frontmatter", b" ---\nalwaysApply: true\n---\n\nbody\n"),
        ("indented-close-frontmatter", b"---\nalwaysApply: true\n ---\n\nbody\n"),
        ("padded-frontmatter", b"---\nalwaysApply: true \n---\n\nbody\n"),
    ):
        check_one_loud_failure(errors, label, content)


def check_one_loud_failure(errors: list[str], label: str, content: bytes | None) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        fake_root = Path(tmp) / "daily-driver"
        (fake_root / "hooks").mkdir(parents=True)
        (fake_root / "rules").mkdir()
        broken = fake_root / "hooks" / SCRIPT.name
        shutil.copy2(SCRIPT, broken)
        if content is not None:
            (fake_root / "rules" / CONSTITUTION.name).write_bytes(content)

        for mode, event, event_name in (
            ("session-start", SESSION_START_EVENT, "SessionStart"),
            ("subagent-start", SUBAGENT_START_EVENT, "SubagentStart"),
        ):
            where = f"{label} constitution, {mode}"
            result = spawn(broken, mode, json.dumps(event))
            if result.returncode != 0:
                errors.append(
                    f"{where}: exited {result.returncode}; the warning rides "
                    f"on stdout, which a nonzero exit puts at risk"
                )
                continue
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError:
                errors.append(f"{where}: stdout is not JSON: {result.stdout[:200]!r}")
                continue

            if "FAILED TO LOAD" not in json.dumps(payload):
                errors.append(
                    f"{where}: the payload does not say the constitution "
                    f"failed to load, so the session would not know"
                )
            if "NOT loaded" not in (payload.get("systemMessage") or ""):
                errors.append(f"{where}: no systemMessage warning for the user")
            if "inject-constitution" not in result.stderr:
                errors.append(f"{where}: nothing on stderr")

            output = payload.get("hookSpecificOutput") or {}
            if output.get("hookEventName") != event_name:
                errors.append(
                    f"{where}: hookEventName is {output.get('hookEventName')!r}"
                )




def collapse(text: str) -> str:
    """Whitespace-collapsed text, so a phrase that straddles a line break matches."""
    return " ".join(text.split())


def check_omp_metadata(errors: list[str]) -> None:
    """The canonical file carries Omp's contract, and the hook delivers its body.

    Omp's acceptance requires two things of a shared source. First, the file
    must announce itself to Omp: `alwaysApply: true` (there is no `agents`
    filter, so this is what makes it reach the main agent *and* every subagent
    from the one `rules/` file). Second, the body Omp injects must be the body
    Claude's hook injects — frontmatter and YAML delimiters stripped —
    or Omp and Claude would disagree about what the constitution says. Both are
    asserted here; the frontmatter check catches drift in the Omp contract, and
    the body check catches the frontmatter leaking into a Claude session.
    """
    body = constitution_body()

    text = CONSTITUTION.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        errors.append(
            "rules/constitution.md has no '---' frontmatter; Omp's rule "
            "provider will not treat it as an Omp rule"
        )
    else:
        try:
            close = next(
                i for i in range(1, len(lines)) if lines[i] == "---"
            )
        except StopIteration:
            errors.append("rules/constitution.md frontmatter is never closed")
        else:
            block = "\n".join(lines[1:close])
            if block != CONSTITUTION_FRONTMATTER:
                errors.append(
                    "rules/constitution.md frontmatter is "
                    f"{block!r}; expected exactly {CONSTITUTION_FRONTMATTER!r} "
                    "for Omp's always-apply rule"
                )

    if "---" in body or CONSTITUTION_FRONTMATTER in collapse(body):
        errors.append(
            "the constitution body still carries its Omp frontmatter; the "
            "hook must deliver the body without YAML delimiters, or Omp and "
            "Claude would receive different texts"
        )

    if not body.strip():
        errors.append("rules/constitution.md is empty after frontmatter")




# Stdin the harness should never send, in the two kinds it comes in: input that
# does not parse, and input that parses into something that is not an event.
# The second kind is the one that looks harmless -- `json.loads` is happy with
# `null`, a list, a bare string, a number -- and then fails at the first
# `.get()`, on the far side of the try/except that was meant to contain it.
BAD_STDIN = ("", "not json at all", "[]", "null", '"hi"', "5")


def check_bad_input(errors: list[str]) -> None:
    """Prevent malformed event input from silently suppressing startup context."""
    for mode, event_name in (
        ("session-start", "SessionStart"),
        ("subagent-start", "SubagentStart"),
    ):
        for stdin in BAD_STDIN:
            payload = bad_input_payload(errors, mode, stdin)
            if payload is None:
                continue
            output = payload.get("hookSpecificOutput") or {}
            if output.get("hookEventName") != event_name:
                errors.append(
                    f"{mode} on {stdin!r}: hookEventName is "
                    f"{output.get('hookEventName')!r}; Codex drops the output "
                    f"of a handler that echoes the wrong event"
                )
            context = output.get("additionalContext")
            if not isinstance(context, str) or "Constitution" not in context:
                errors.append(f"{mode} on {stdin!r}: no constitution in the output")



def bad_input_payload(errors: list[str], mode: str, stdin: str) -> dict | None:
    """Run a mode on unusable stdin; report and return None unless it survives."""
    where = f"{mode} on {stdin!r}"
    result = spawn(SCRIPT, mode, stdin)
    if result.returncode != 0:
        errors.append(
            f"{where}: exited {result.returncode}, costing the session its "
            f"constitution over a bad event\n  stderr: "
            f"{result.stderr.strip() or '(empty)'}"
        )
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        errors.append(f"{where}: stdout is not JSON: {result.stdout[:200]!r}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{where}: emitted {type(payload).__name__}, not an object")
        return None
    return payload


def check_bad_argv(errors: list[str]) -> None:
    """Prevent obsolete or misspelled modes from silently accepting a bad route."""
    for mode in ("no-such-mode", "", "session_start", "pre-tool-use"):
        result = spawn(SCRIPT, mode, "{}")
        if result.returncode == 0:
            errors.append(
                f"the mode {mode!r} exited 0; a typo in hooks.json would be "
                f"silent"
            )


def main() -> int:
    errors: list[str] = []
    try:
        check_wiring(errors)
        check_delivery(errors)
        check_loud_failure(errors)
        check_omp_metadata(errors)
        check_bad_input(errors)
        check_bad_argv(errors)
    except Failed as failure:
        errors.append(str(failure))

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(
        "constitution delivery holds: every injection point carries "
        f"{CONSTITUTION.relative_to(ROOT)}'s body verbatim, identically, on "
        "both harnesses, and fails loudly when it is missing or malformed"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
