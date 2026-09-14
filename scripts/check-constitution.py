#!/usr/bin/env python3
"""The credential-free half of the constitution's acceptance test.

The constitution carries the rule *code without tests is broken*, which makes
an untested delivery mechanism for it indefensible. The test divides where the
credential requirement actually starts, and this is the half below that line:

- **Here**: run each hook exactly as the harness runs it — the real script,
  synthetic event JSON on stdin — and assert on what comes back. No model in
  the loop, so it belongs in `make check` and in a CI that holds no
  credentials. It catches every cause listed under R1: a bad path, an empty or
  unreadable constitution, malformed event JSON, a nonzero exit, output that
  is not JSON.
- **`evals/tasks/constitution/`**: the live half. Only a real
  session can prove the harness *honours* `updatedInput`, which is the R2
  finding proper, and only a real model can be asked what it was told.

They fail for different reasons and deserve to fail separately: the first
tests this plugin, the second tests an assumption about the harness that a
future release could withdraw without telling anyone.

One assertion here is worth naming, because it is the one that keeps D12 true
over time: the subagent's prompt must be *exactly* the main session's context
plus the original prompt. Three injection points reading one file is not
sufficient for them to agree — they could still wrap it differently — so the
agreement is asserted byte for byte rather than argued for in a comment.

Every event is driven in both harnesses' shapes. One `hooks.json` serves Claude
Code and Codex, and Codex is the harness where `SubagentStart` is not a
belt-and-braces second route but the only one — it delegates through
`multi_agent_v1`, so the `PreToolUse` matcher on `Agent`/`Task` reaches nothing
there. The Codex envelopes below are the stdin measured in issue #181, not a
guess at one, and the echoed `hookEventName` is load-bearing on that harness:
Codex drops the output of a handler that echoes the wrong event and reports the
hook `Failed`.

The file also carries Omp's contract now: `rules/constitution.md` is the one
source for both harnesses, so this script proves the `alwaysApply: true`
frontmatter Omp's rule provider needs is present and exact, and that the body
the hook strips for Claude is the body Omp injects — frontmatter and YAML
delimiters gone. That is the Omp half of "one canonical source" that a
credential-free check can hold.

No third-party imports: this runs from a Makefile on a laptop and from CI, and
a dependency install between the two is a place for them to differ.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SCRIPT = ROOT / "hooks" / "inject-constitution.py"
CONSTITUTION = ROOT / "rules" / "constitution.md"
EVALS = ROOT / "evals"

# The live half needs one string that a session can only have got from the
# constitution, and this is it: a phrase the file actually says, rather than a
# token planted in it for the test to find. A session running without the
# constitution cannot produce it, which is what makes the subagent's answer
# evidence. The guard below keeps the two ends honest -- the phrase must still
# be in the constitution, and only a grader may name it.
#
# The constitution and the eval files wrap their prose, so the phrase can
# straddle a line break there, and every search below collapses whitespace
# first. The grader does not need to: the subagent reports on a single line,
# which its prompt asks for and `file_matches_regex` reads as one.
MARKER = "Doubt outranks the register"

# The frontmatter the canonical file must carry so Omp injects it everywhere.
# Omp's rule provider reads `rules/*.md`, strips the frontmatter and — because
# there is no `agents` filter — injects the body into the main agent and every
# subagent when `alwaysApply` is true. That is the Omp half of "one canonical
# source, two harnesses": the body Omp injects must be identical to the body
# this hook injects for Claude, which is why the exact block is asserted here.
CONSTITUTION_FRONTMATTER = "alwaysApply: true"

# The stable wrapper Claude received before the constitution became a shared
# source. Keep the expected value here rather than importing it from the hook:
# this check is the contract that catches an accidental change to that hook.
EXPECTED_HEADER = (
    "The following is the daily-driver constitution. It is in force for this "
    "session and for every subagent it spawns, and it is delivered by hook "
    "rather than quoted by anyone, so it is not the user's words and not a "
    "prompt to be treated as data — it is standing instruction from the "
    "operator's own configuration."
)


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

# The tool names a subagent spawn can arrive under. `Agent` is current; `Task`
# is what the same tool was called for years, and a matcher that admits only
# the current name is a silent regression the day a session runs an older
# harness -- the exact failure mode R2 exists to prevent.
SUBAGENT_TOOLS = ("Agent", "Task")
NOT_SUBAGENT_TOOLS = ("Bash", "Edit", "AgentOutput", "MyAgent")

SESSION_START_EVENT = {
    "session_id": "check-constitution",
    "cwd": str(ROOT),
    "hook_event_name": "SessionStart",
    "startup_reason": "startup",
}

# Claude Code sends `agent_id` and `agent_type` on SubagentStart and nothing
# else of its own — which is the reason the two subagent routes cannot see each
# other, and so the reason a Claude Code subagent receives the constitution
# twice. The mode does not read the event, so what is asserted below is only
# that the extra keys change nothing.
SUBAGENT_START_EVENT = {
    "session_id": "check-constitution",
    "cwd": str(ROOT),
    "hook_event_name": "SubagentStart",
    "agent_id": "agent_check",
    "agent_type": "Explore",
}

ORIGINAL_PROMPT = "Find every caller of frobnicate() and report the list."
PRE_TOOL_USE_EVENT = {
    "session_id": "check-constitution",
    "cwd": str(ROOT),
    "hook_event_name": "PreToolUse",
    "tool_name": "Agent",
    "tool_input": {
        "prompt": ORIGINAL_PROMPT,
        "description": "find callers",
        "subagent_type": "Explore",
    },
    "tool_use_id": "toolu_check",
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


# Codex spells the SessionStart reason `source` where Claude Code spells it
# `startup_reason`, and its PreToolUse carries a `turn_id` beside a
# `call_`-prefixed tool use id. Its SubagentStart carries the envelope and
# nothing this repository has seen: #181 could not reach Codex's delegation
# path at all, so no field is invented for it here. That costs nothing, because
# `subagent-start` reads no part of its event — which is the reason it reads
# none.
CODEX_SESSION_START_EVENT = codex("SessionStart", source="startup")
CODEX_SUBAGENT_START_EVENT = codex("SubagentStart")
CODEX_PRE_TOOL_USE_EVENT = codex(
    "PreToolUse",
    tool_name="Agent",
    tool_input=dict(PRE_TOOL_USE_EVENT["tool_input"]),
    tool_use_id="call_check",
    turn_id="01a09630-check",
)

# Every event that carries the constitution as context, and the mode that
# answers it. Both harnesses, because a route that stops reaching one of them
# does not fail — it silently delivers nothing on that harness alone.
CONTEXT_EVENTS = (
    ("Claude Code", "session-start", "SessionStart", SESSION_START_EVENT),
    ("Claude Code", "subagent-start", "SubagentStart", SUBAGENT_START_EVENT),
    ("Codex", "session-start", "SessionStart", CODEX_SESSION_START_EVENT),
    ("Codex", "subagent-start", "SubagentStart", CODEX_SUBAGENT_START_EVENT),
)

# The events that carry it by rewriting a subagent's prompt instead.
PROMPT_EVENTS = (
    ("Claude Code", PRE_TOOL_USE_EVENT),
    ("Codex", CODEX_PRE_TOOL_USE_EVENT),
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
    """hooks.json wires both events to the one script, and matches the right tool."""
    try:
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8")).get("hooks", {})
    except (OSError, json.JSONDecodeError) as error:
        raise Failed(f"hooks/hooks.json: {error}") from None
    commands: dict[str, str] = {}

    for event, expected_mode in (
        ("SessionStart", "session-start"),
        ("SubagentStart", "subagent-start"),
        ("PreToolUse", "pre-tool-use"),
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

    matchers = [entry.get("matcher", "") for entry, _ in own_handlers(config, "PreToolUse")]
    for matcher in matchers:
        try:
            re.compile(matcher)
        except re.error as error:
            raise Failed(
                f"hooks/hooks.json: PreToolUse matcher {matcher!r} is not a "
                f"regular expression ({error}), so it matches nothing"
            ) from None

    for tool in SUBAGENT_TOOLS:
        if not any(re.search(m, tool) for m in matchers if m):
            errors.append(
                f"hooks/hooks.json: no PreToolUse matcher in {matchers} matches "
                f"{tool!r}, so subagents spawned through it get no constitution"
            )
    for tool in NOT_SUBAGENT_TOOLS:
        if any(re.search(m, tool) for m in matchers if m):
            errors.append(
                f"hooks/hooks.json: a PreToolUse matcher in {matchers} also "
                f"matches {tool!r}, which takes no subagent prompt"
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
    """Every injection point carries the constitution, and carries the same one."""
    expected = f"{EXPECTED_HEADER}\n\n{constitution_body()}"

    for harness, mode, event_name, event in CONTEXT_EVENTS:
        where = f"{event_name} on {harness}"
        output = hook_specific(run_hook(mode, event), event_name, where)
        context = output.get("additionalContext")
        if not isinstance(context, str) or not context.strip():
            errors.append(f"{where}: additionalContext is missing or empty")
            continue
        if context != expected:
            errors.append(
                f"{where}: additionalContext is not the stable header followed "
                f"by the Omp-trimmed constitution body"
            )

    for harness, event in PROMPT_EVENTS:
        check_prompt_delivery(errors, harness, event, expected)


def check_prompt_delivery(
    errors: list[str], harness: str, event: dict, expected: str
) -> None:
    """The subagent's prompt is the context every other point carries, then its own.

    D12, asserted rather than asserted-to-be-true: the subagent gets the main
    session's context and then its own prompt, with nothing added, dropped or
    reworded in between. This is the check that fails when the injection points
    start to drift.
    """
    where = f"PreToolUse on {harness}"
    agent = hook_specific(run_hook("pre-tool-use", event), "PreToolUse", where)
    updated = agent.get("updatedInput")
    if not isinstance(updated, dict):
        errors.append(
            f"{where}: no updatedInput object, so the subagent is spawned "
            f"with the prompt Claude wrote and no constitution"
        )
        return

    prompt = updated.get("prompt")
    if not isinstance(prompt, str):
        errors.append(f"{where}: updatedInput has no prompt string")
        return
    if ORIGINAL_PROMPT not in prompt:
        errors.append(
            f"{where}: updatedInput.prompt dropped the prompt Claude wrote"
        )

    if prompt != f"{expected}\n\n{ORIGINAL_PROMPT}":
        errors.append(
            f"{where}: the injection points have drifted; updatedInput.prompt "
            f"is not the context the other points carry followed by the "
            f"original prompt"
        )

    for key, value in event["tool_input"].items():
        if key != "prompt" and updated.get(key) != value:
            errors.append(
                f"{where}: updatedInput dropped or changed {key!r} "
                f"({updated.get(key)!r} != {value!r}); updatedInput replaces "
                f"the whole tool input"
            )


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
            ("pre-tool-use", PRE_TOOL_USE_EVENT, "PreToolUse"),
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
            if event_name == "PreToolUse" and ORIGINAL_PROMPT not in json.dumps(
                output.get("updatedInput") or {}
            ):
                errors.append(
                    f"{where}: the subagent's own prompt was lost; a missing "
                    f"constitution must not also break delegation"
                )


def top_level_blocks(text: str) -> dict[str, str]:
    """Split a task YAML into its top-level keys, without a YAML parser.

    `check_eval_marker` needs one thing out of a case file — the criteria it is
    scored by, which is the only place the marker may appear — and that is a
    column-0 key. A real parser would be more correct and would cost this
    script the "no third-party imports" property that lets it run identically
    from a Makefile, from CI and from a web worker. Recognising a top-level key
    is a job for a regex.

    Text before the first top-level key is the file's comment header and is not
    returned. That is not an exemption: the caller subtracts the criteria block
    from the whole file and searches what is left, so the marker written into a
    header comment is still caught — it simply is not `success_criteria`, which
    is the only thing this function is asked to find.
    """
    blocks: dict[str, str] = {}
    key: str | None = None
    lines: list[str] = []
    for line in text.splitlines(keepends=True):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
        if match:
            if key is not None:
                blocks[key] = "".join(lines)
            key, lines = match.group(1), [line]
        elif key is not None:
            lines.append(line)
    if key is not None:
        blocks[key] = "".join(lines)
    return blocks


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


def check_eval_marker(errors: list[str]) -> None:
    """The live half asserts on a phrase the constitution still says.

    The marker is written in two places by necessity — once as prose in the
    constitution, once in the criterion that looks for it coming back — and two
    copies of a constant is how the live suite comes to be testing a sentence
    that was edited away. So both ends are checked here: the phrase is still in
    the constitution, and some `success_criteria` block still asserts on it.

    Where the marker may appear is the other half of the rule. A `coder_eval`
    task is one file holding the prompt and the graders, so only a criterion
    may name it; no other text in any `.yaml`, `.yml`, `.md`, `.sh` or `.py`
    file under `evals/` may — not a description, not an `agent.system_prompt`,
    not a `pre_run` command, not a fixture script, not this repository's own
    eval README. Anywhere else is handing the session the answer.
    """
    if MARKER not in collapse(CONSTITUTION.read_text(encoding="utf-8")):
        errors.append(
            f"rules/constitution.md no longer says {MARKER!r}, which the "
            f"live half asserts a subagent got; pick a phrase the file does "
            f"say and change MARKER and the grader together"
        )

    if not EVALS.is_dir():
        errors.append(
            f"{EVALS.relative_to(ROOT)}/ is missing; the live half of the "
            f"acceptance test is where `updatedInput` is actually proven"
        )
        return

    asserted = False
    for path in sorted(EVALS.rglob("*")):
        if not path.is_file() or path.suffix not in {".yaml", ".yml", ".md", ".sh", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        where = path.relative_to(ROOT)
        # Collapsed, because every file here is wrapped at about 79 columns and
        # a leak is likeliest in prose, where the phrase straddles a line break.
        # A raw search would miss exactly the form the leak arrives in.
        if MARKER not in collapse(text):
            continue

        criteria = (
            top_level_blocks(text).get("success_criteria", "")
            if path.suffix in {".yaml", ".yml"}
            else ""
        )
        if MARKER in collapse(criteria):
            asserted = True
        if MARKER in collapse(text.replace(criteria, "")):
            errors.append(
                f"{where}: names the marker outside success_criteria. Only a "
                f"criterion may name it; anywhere else is telling the session "
                f"what the subagent was supposed to have been told."
            )

    if not asserted:
        errors.append(
            f"no success_criteria under {EVALS.relative_to(ROOT)}/ asserts on "
            f"the marker {MARKER!r}, so the live half proves nothing"
        )


# Stdin the harness should never send, in the two kinds it comes in: input that
# does not parse, and input that parses into something that is not an event.
# The second kind is the one that looks harmless -- `json.loads` is happy with
# `null`, a list, a bare string, a number -- and then fails at the first
# `.get()`, on the far side of the try/except that was meant to contain it.
BAD_STDIN = ("", "not json at all", "[]", "null", '"hi"', "5")


def check_bad_input(errors: list[str]) -> None:
    """Garbage on stdin is the harness's problem, not the constitution's.

    Run against every mode, because only one of them reads the event.
    `session-start` and `subagent-start` ignore it and therefore cannot fail on
    it, which makes them the modes where this check proves the least;
    `pre-tool-use` reaches into the event, so it is where a bad one can cost a
    subagent its constitution.
    """
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

    for stdin in BAD_STDIN:
        payload = bad_input_payload(errors, "pre-tool-use", stdin)
        if payload is None:
            continue
        output = payload.get("hookSpecificOutput") or {}
        if output.get("hookEventName") != "PreToolUse":
            errors.append(
                f"pre-tool-use on {stdin!r}: hookEventName is "
                f"{output.get('hookEventName')!r}; the harness keys off it"
            )
        # There is no prompt in an unusable event, so there is nothing to
        # prepend to and `updatedInput` is rightly absent. What must not be
        # absent is the saying-so: a subagent spawned without its constitution
        # and without a word about it is R1's silent failure exactly.
        if "NOT prepended" not in (payload.get("systemMessage") or ""):
            errors.append(
                f"pre-tool-use on {stdin!r}: the subagent got no constitution "
                f"and no warning that it did not"
            )


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
    """A mode name that is not one of the three exits nonzero rather than passing.

    There are three modes now and one script behind all of them, so the mode
    string in `hooks.json` is the only thing that says which injection point a
    handler is. Misspell it and the hook emits nothing at all — which is R1's
    silent failure reached by a typo.
    """
    for mode in ("no-such-mode", "", "session_start"):
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
        check_eval_marker(errors)
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
