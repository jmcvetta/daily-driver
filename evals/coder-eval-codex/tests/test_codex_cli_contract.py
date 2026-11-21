#!/usr/bin/env python3
"""Offline contract tests for the Codex CLI adapter.

Everything here runs without `codex`, without coder_eval and without network
access. That is deliberate: the driver cannot start in CI, so the parts that
decide what a stream means, how a login is classified, and where a skill is
linked are kept in modules that import nothing and are exercised here.

The failures these tests would catch are silent in production:

* a usage-bucket mapping that counts cached tokens as fresh, inflating cost and
  tripping a token budget early;
* a `turn.failed` treated as a transient `error`, scoring a dead turn;
* a relative plugin root linked back at itself, so the treated arm runs with no
  skills and reports zeros;
* a login sentence misread as the subscription when it is an API key.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from coder_eval_codex.discovery import classify_auth, model_slugs  # noqa: E402
from coder_eval_codex.events import (  # noqa: E402
    Usage,
    token_counts,
    token_delta,
    TurnAccumulator,
)
from coder_eval_codex.skills import SkillLinkError, link_skills  # noqa: E402
from coder_eval_codex.transcript import render_agent_output  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_documented_stream() -> None:
    """The published sample plus a tool call reduces to the record's values."""
    lines = [
        '{"type":"thread.started","thread_id":"0199a213-81c0-7800-8aa1-bbab2a035a53"}',
        '{"type":"turn.started"}',
        '{"type":"item.started","item":{"id":"item_1","type":"command_execution",'
        '"command":"bash -lc ls","status":"in_progress"}}',
        '{"type":"item.completed","item":{"id":"item_1","type":"command_execution",'
        '"command":"bash -lc ls","status":"completed","exit_code":0}}',
        '{"type":"item.completed","item":{"id":"item_3","type":"agent_message",'
        '"text":"Repo contains docs, sdk, and examples directories."}}',
        '{"type":"turn.completed","usage":{"input_tokens":24763,'
        '"cached_input_tokens":24448,"output_tokens":122,"reasoning_output_tokens":8}}',
    ]
    accumulator = TurnAccumulator()
    produced = [event for line in lines for event in accumulator.feed_line(line)]

    check(accumulator.thread_id == "0199a213-81c0-7800-8aa1-bbab2a035a53", "thread id not captured")
    check(accumulator.turns_started == 1, "turn.started not counted")
    check(accumulator.turns_completed == 1, "turn.completed not counted")
    check(accumulator.failure is None, "a clean stream reported a failure")

    kinds = [event.kind for event in produced]
    check(kinds.count("item_started") == 1 and kinds.count("item_completed") == 2, f"item events wrong: {kinds}")
    command = next(event.value for event in produced if event.kind == "item_completed" and event.value.type == "command_execution")
    check(command.command == "bash -lc ls" and command.exit_code == 0, f"command item wrong: {command}")
    message = next(event.value for event in produced if event.kind == "item_completed" and event.value.type == "agent_message")
    check(message.text == "Repo contains docs, sdk, and examples directories.", f"message wrong: {message}")

    counts = token_counts(accumulator.usage)
    check(counts.uncached_input_tokens == 315, f"fresh input should be 24763-24448, got {counts.uncached_input_tokens}")
    check(counts.cache_read_input_tokens == 24448, f"cached input wrong: {counts.cache_read_input_tokens}")
    check(counts.output_tokens == 130, f"reasoning must fold into output, got {counts.output_tokens}")
    check(counts.cache_creation_input_tokens == 0, "OpenAI reports no cache-write bucket")


def test_transient_error_is_not_a_failure() -> None:
    """A reconnect notice followed by a completed turn is a completed turn."""
    accumulator = TurnAccumulator()
    accumulator.feed_line('{"type":"thread.started","thread_id":"t"}')
    accumulator.feed_line('{"type":"error","message":"Reconnecting... 2/5 (401)"}')
    accumulator.feed_line('{"type":"turn.started"}')
    accumulator.feed_line('{"type":"turn.completed","usage":{"input_tokens":10,"cached_input_tokens":0,"output_tokens":1,"reasoning_output_tokens":0}}')
    check(accumulator.failure is None, "a transient error must not set the terminal failure")
    check(accumulator.turns_completed == 1, "the completed turn was lost")
    check(len(accumulator.errors) == 1, "the diagnostic should still be recorded")


def test_turn_failed_is_terminal() -> None:
    accumulator = TurnAccumulator()
    accumulator.feed_line('{"type":"turn.started"}')
    accumulator.feed_line('{"type":"turn.failed","error":{"message":"quota exhausted"}}')
    check(accumulator.failure == "quota exhausted", f"failure not recorded: {accumulator.failure}")
    check(accumulator.turns_completed == 0, "a failed turn must not count as completed")


def test_unknown_types_are_bounded() -> None:
    accumulator = TurnAccumulator()
    for index in range(20):
        accumulator.feed({"type": f"future.event.{index}"})
    check(len(accumulator.unrecognized_types) == 8, f"sample should be bounded, got {accumulator.unrecognized_types}")
    check(accumulator.recognized == 0, "unknown envelopes must not count as recognized")


def test_tool_status_prefers_exit_code() -> None:
    """`status: completed` must not mask a failed shell exit."""
    from coder_eval_codex.events import Item, tool_status

    failed = Item(id="1", type="command_execution", status="completed", command="false", exit_code=1)
    check(tool_status(failed, completed=True) == "error", "non-zero exit recorded as success")
    ok = Item(id="2", type="command_execution", status="completed", command="true", exit_code=0)
    check(tool_status(ok, completed=True) == "success", "zero exit recorded as error")
    no_code = Item(id="3", type="file_change", status="completed")
    check(tool_status(no_code, completed=True) == "success", "status fallback lost")
    pending = Item(id="4", type="command_execution", status="in_progress")
    check(tool_status(pending, completed=False) == "unknown", "an unfinished tool was scored")


def test_usage_delta_never_goes_negative() -> None:
    previous = Usage(input_tokens=100, cached_input_tokens=40, output_tokens=10, reasoning_output_tokens=2)
    current = Usage(input_tokens=90, cached_input_tokens=50, output_tokens=8, reasoning_output_tokens=1)
    delta = token_delta(current, previous)
    check(delta.uncached_input_tokens == 0, f"negative fresh input not clamped: {delta}")
    check(delta.output_tokens == 0, f"negative output not clamped: {delta}")
    check(delta.cache_read_input_tokens == 10, f"cache delta wrong: {delta}")


def test_login_classification_fails_closed() -> None:
    check(classify_auth("Not logged in") == "none", "missing login not recognized")
    check(classify_auth("Logged in using ChatGPT") == "subscription", "subscription login not recognized")
    check(classify_auth("Logged in with an API key") == "api_key", "API key not recognized")
    check(classify_auth("Something entirely new") == "unknown", "unrecognized login must be unknown")
    check(classify_auth("") == "unknown", "empty login must be unknown")


def test_model_catalog_parsing() -> None:
    sample = json.dumps({"models": [{"slug": "gpt-6.1-sol"}, {"slug": "gpt-6-luna"}, {"nope": True}]})
    check(model_slugs(sample) == ["gpt-6.1-sol", "gpt-6-luna"], "catalog entries lost")
    check(model_slugs("not json") == [], "unparseable catalog must be empty, not guessed")
    check(model_slugs('{"models": {}}') == [], "wrong shape must be empty")


def test_skills_link_from_a_relative_plugin_root() -> None:
    """The SDK defect: a relative root linked every skill back at itself."""
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp) / "evals"
        workspace = Path(tmp) / "task"
        plugin = base / "plugin"
        for name in ("pr", "pr-title"):
            skill = plugin / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {name}\n---\n", encoding="utf-8")
        workspace.mkdir()

        linked = link_skills([{"type": "local", "path": "plugin"}], base=base, workspace=workspace)
        check(linked == ["pr", "pr-title"], f"linked names wrong: {linked}")
        for name in linked:
            link = workspace / ".agents" / "skills" / name
            check(link.is_symlink(), f"{name} was not linked")
            check((link / "SKILL.md").is_file(), f"{name}'s SKILL.md is unreadable through the link")


def test_skills_without_a_readable_skill_is_fatal() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        workspace = base / "task"
        (base / "empty-plugin").mkdir()
        workspace.mkdir()
        try:
            link_skills([{"type": "local", "path": "empty-plugin"}], base=base, workspace=workspace)
        except SkillLinkError:
            return
        raise AssertionError("a declared plugin with no skill must raise, not run untreated")


def test_transcript_carries_the_judge_anchor() -> None:
    rendered = render_agent_output("Repo contains docs.")
    check("[RESULT - SUCCESS]" in rendered, f"the judge's anchor is missing: {rendered!r}")
    check("Repo contains docs." in rendered, "the reply was lost in rendering")


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    failed = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {test.__name__}: {exc}", file=sys.stderr)
        else:
            print(f"ok   {test.__name__}")
    if failed:
        print(f"{failed} of {len(tests)} checks failed", file=sys.stderr)
        return 1
    print(f"all {len(tests)} checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
