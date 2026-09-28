#!/usr/bin/env python3
"""The acceptance test for the Omp eval arm's frame reduction.

`evals/coder-eval-omp/` teaches `coder_eval` to run the eval suites against
Omp. Almost none of that package can be exercised in `make check`: it needs a
`coder-eval` install and an `omp` binary, and CI here has neither. So the parts
that decide whether a row scores at all live in `coder_eval_omp/rpc.py`, which
imports nothing, and this script drives them against recorded frames.

WHAT IT ASSERTS

    A `read` of `skill://<name>` becomes a canonical `Skill` call. This is the
    whole reason the arm needs an adapter: `skill_triggered` detects a skill by
    the substring `skills/<name>/` or by a `Skill` tool call, and Omp's skill
    URL carries neither. Unmapped, every positive row in the Omp arm scores 0,
    which reads exactly like a plugin that never loaded.
    Omp's tool names and argument keys arrive in the canonical vocabulary, and
    an unknown tool passes through under its own name rather than vanishing.
    Arguments that arrive late -- on `tool_execution_update` rather than on
    `tool_execution_start` -- still reach the telemetry. Omp's docs do not say
    which frame carries them, so the reduction must accept either.
    A turn settles on a terminal `agent_end` and not on one carrying
    `isTerminal: false`.
    The transcript the judge reads carries the `[RESULT - ...]` anchor. Every
    `llm_judge` rubric under `evals/tasks/` locates the reply at that tag and
    scores 0.0 without it, deliberately and with no fallback -- so an arm that
    handed the judge bare text would fail every judged row in both arms.
    A frame type outside the known vocabulary is recorded as drift, while the
    routine frames that imply no action are not.

WHAT IT DOES NOT ASSERT

    That `omp` starts, that the plugin installs, or that a skill fires. The
    first two are `make check-omp-plugin`'s, which drives a real binary; the
    third needs a model and is what `evals/` is for.
    That the field names this module reads are the ones a live Omp emits. The
    reduction reads every plausible spelling and records which one answered, in
    `omp_argument_keys_seen` and `omp_usage_keys_seen` on the run's
    environment info. The first live run is what settles that, and this script
    cannot.

No third-party imports, for the reason `check-manifests.py` gives: a dependency
install between the laptop and CI is a place for them to differ.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PACKAGE_SRC = ROOT / "evals" / "coder-eval-omp" / "src"

sys.path.insert(0, str(PACKAGE_SRC))

from coder_eval_omp import pricing  # noqa: E402  (the path insert must come first)
from coder_eval_omp.rpc import (  # noqa: E402
    AgentFinished,
    ToolFinished,
    ToolStarted,
    TurnReducer,
    canonical_tool_call,
    extract_usage,
    render_agent_output,
    skill_name_from_url,
)

# A `message_end` frame shaped like a real Omp RPC session's assistant
# message. Reconstructed from the shipped `@oh-my-pi/{pi-ai,pi-agent-core,
# pi-coding-agent}@18.4.2` TypeScript source (see `rpc.py`'s module
# docstring) rather than sampled from a live run: no `omp` binary or session
# reaches CI or this repository's own development environment. Every field
# below is required by that source or copied from it, not guessed; only the
# reply text is a placeholder.
ASSISTANT_MESSAGE_END_FRAME = {
    "type": "message_end",
    "messageId": "msg-1",
    "message": {
        "role": "assistant",
        "content": [{"type": "text", "text": "done"}],
        "api": "anthropic-messages",
        "provider": "vercel-ai-gateway",
        "model": "zai/glm-5.3",
        "usage": {"input": 812, "output": 143, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 955},
        "stopReason": "stop",
    },
}


class CheckFailed(Exception):
    """A failed assertion, with the detail that explains it."""


def check(condition: bool, message: str) -> None:
    """Fail the whole script on a false condition, naming what was expected."""
    if not condition:
        raise CheckFailed(message)


def feed(reducer: TurnReducer, *frames: dict) -> list:
    """Feed several frames, returning every action they produced, in order."""
    actions: list = []
    for frame in frames:
        actions.extend(reducer.feed(frame))
    return actions


def check_skill_urls() -> None:
    """`skill://<name>` names the skill, whatever follows it."""
    check(skill_name_from_url("skill://pr-title") == "pr-title", "a bare skill URL names its skill")
    check(
        skill_name_from_url("skill://pr-title/references/omp.md") == "pr-title",
        "a skill URL with a path inside the skill still names the skill",
    )
    check(skill_name_from_url("/home/x/skills/pr/SKILL.md") is None, "a file path is not a skill URL")
    check(skill_name_from_url("skill://") is None, "an empty skill URL names nothing")


def check_canonical_calls() -> None:
    """Omp's vocabulary arrives as Claude's, and the skill read arrives as `Skill`."""
    name, params = canonical_tool_call("read", {"url": "skill://judgement-call"})
    check(
        (name, params) == ("Skill", {"skill": "judgement-call"}),
        f"a read of a skill URL must become a Skill call, got {name} {params}",
    )

    name, params = canonical_tool_call("read", {"path": "/repo/skills/pr/SKILL.md"})
    check(name == "Read", "read maps to Read")
    check(
        params == {"file_path": "/repo/skills/pr/SKILL.md"},
        f"Omp's `path` must arrive as Claude's `file_path`, got {params}",
    )

    name, params = canonical_tool_call("bash", {"command": "git status"})
    check((name, params) == ("Bash", {"command": "git status"}), "bash maps to Bash with its command intact")

    name, _ = canonical_tool_call("task", {"prompt": "review this"})
    check(name == "Agent", "task maps to Agent")

    name, params = canonical_tool_call("some_new_omp_tool", {"whatever": 1})
    check(
        (name, params) == ("some_new_omp_tool", {"whatever": 1}),
        "an unmapped tool passes through under its own name rather than vanishing",
    )


def check_tool_lifecycle() -> None:
    """A tool call reduces to one start and one end, with late arguments honored."""
    reducer = TurnReducer()
    actions = feed(
        reducer,
        {"type": "tool_execution_start", "toolCallId": "c1", "toolName": "bash"},
        {"type": "tool_execution_update", "toolCallId": "c1", "args": {"command": "make check"}},
        {"type": "tool_execution_end", "toolCallId": "c1", "result": "ok"},
    )
    starts = [a for a in actions if isinstance(a, ToolStarted)]
    ends = [a for a in actions if isinstance(a, ToolFinished)]
    check(len(starts) == 1 and len(ends) == 1, f"one start and one end expected, got {actions}")
    check(
        starts[0].parameters == {"command": "make check"},
        f"arguments arriving on the update frame must reach the telemetry, got {starts[0].parameters}",
    )
    check(ends[0].status == "ok", "a result with no error is ok")
    check("args" in reducer.argument_keys_seen, "the argument key that answered is recorded")

    reducer = TurnReducer()
    ends = [
        a
        for a in feed(
            reducer,
            {"type": "tool_execution_start", "toolCallId": "c2", "toolName": "bash", "args": {"command": "false"}},
            {"type": "tool_execution_end", "toolCallId": "c2", "error": "exit 1"},
        )
        if isinstance(a, ToolFinished)
    ]
    check(ends and ends[0].status == "error", "a result carrying an error is an error")

    reducer = TurnReducer()
    feed(reducer, {"type": "tool_execution_start", "toolCallId": "c3", "toolName": "read"})
    orphans = reducer.close_open_tools()
    check(
        len(orphans) == 1 and orphans[0].status == "unresolved",
        "a tool with no result is force-closed as unresolved",
    )


def check_skill_engagement_end_to_end() -> None:
    """The whole path a skill engagement takes, from frame to canonical call."""
    reducer = TurnReducer()
    actions = feed(
        reducer,
        {
            "type": "tool_execution_start",
            "toolCallId": "s1",
            "toolName": "read",
            "args": {"url": "skill://undertake"},
        },
    )
    starts = [a for a in actions if isinstance(a, ToolStarted)]
    check(len(starts) == 1, "the skill read produces one tool start")
    check(starts[0].tool_name == "Skill", f"the skill read is a Skill call, got {starts[0].tool_name}")
    check(
        starts[0].parameters == {"skill": "undertake"},
        f"`skill_triggered` reads parameters['skill'], got {starts[0].parameters}",
    )
    check(starts[0].raw_tool_name == "read", "Omp's own tool name is kept for the report")


def check_turn_settlement() -> None:
    """Only a terminal `agent_end` settles a turn."""
    reducer = TurnReducer()
    actions = feed(reducer, {"type": "agent_end", "isTerminal": False, "messages": []})
    ends = [a for a in actions if isinstance(a, AgentFinished)]
    check(ends and ends[0].terminal is False, "isTerminal false does not settle the turn")

    actions = feed(reducer, {"type": "agent_end", "messages": []})
    ends = [a for a in actions if isinstance(a, AgentFinished)]
    check(ends and ends[0].terminal is True, "an agent_end with no isTerminal field is terminal")


def check_usage() -> None:
    """Token counts come from an assistant message's `usage`, read at `message_end`."""
    usage, seen = extract_usage(ASSISTANT_MESSAGE_END_FRAME["message"])
    check(
        usage
        == {
            "uncached_input_tokens": 812,
            "output_tokens": 143,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        f"`input`/`output`/`cacheRead`/`cacheWrite` must map to coder_eval's buckets, got {usage}",
    )
    check(
        sorted(seen) == ["cacheRead", "cacheWrite", "input", "output"],
        f"the fields read are recorded, got {seen}",
    )

    # The field missing entirely, and the whole object missing: both report
    # nothing found rather than zeros. `require_token_telemetry` turns this
    # into a crash in `agent.py`, which -- like the rest of that module --
    # needs a `coder_eval` install and an `omp` binary this script has
    # neither of, so the crash itself is outside what `make check` can drive;
    # this is the empty result that check exists to fail loudly on.
    usage, seen = extract_usage({"role": "assistant", "content": []})
    check(usage == {} and seen == [], "an assistant message with no `usage` object reports none, not zeros")

    usage, seen = extract_usage({"role": "assistant", "usage": {"input": 5}})
    check(
        usage == {"uncached_input_tokens": 5} and seen == ["input"],
        f"a `usage` object missing a bucket reports only what it has, got {usage} {seen}",
    )

    # The reducer: usage accumulates from `message_end` only. A
    # `message_update`'s `message` is a streaming snapshot whose `usage` is
    # not yet final, so counting it too would double every total.
    reducer = TurnReducer()
    feed(
        reducer,
        {
            "type": "message_update",
            "messageId": "m1",
            "message": {"role": "assistant", "usage": {"input": 999, "output": 999, "cacheRead": 0, "cacheWrite": 0}},
        },
        ASSISTANT_MESSAGE_END_FRAME,
    )
    check(
        reducer.usage
        == {
            "uncached_input_tokens": 812,
            "output_tokens": 143,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
        f"only the `message_end` usage must be counted, got {reducer.usage}",
    )

    actions = feed(reducer, {"type": "agent_end", "messages": []})
    ends = [a for a in actions if isinstance(a, AgentFinished)]
    check(
        ends and ends[0].usage == reducer.usage,
        "agent_end must report the usage accumulated across the run, not read its own (absent) usage",
    )

    # A message an aborted turn never individually streamed surfaces instead
    # in `agent_end`'s own `messages` array (`RpcFrameEncoder.
    # compactTerminalFrame`, `rpc-frame.ts`, 18.4.2, trims it to exactly the
    # not-yet-streamed tail) -- the shape `check-omp-agent-settle.py`'s fake
    # `omp` scenario has exercised since before this file existed.
    reducer = TurnReducer()
    actions = feed(
        reducer,
        {
            "type": "agent_end",
            "isTerminal": True,
            "messages": [
                {"role": "assistant", "usage": {"input": 22586, "output": 47, "cacheRead": 10, "cacheWrite": 0}},
            ],
        },
    )
    ends = [a for a in actions if isinstance(a, AgentFinished)]
    check(
        ends
        and ends[0].usage
        == {
            "uncached_input_tokens": 22586,
            "output_tokens": 47,
            "cache_read_input_tokens": 10,
            "cache_creation_input_tokens": 0,
        },
        f"a message settling only in `agent_end.messages` must still be counted, got {ends[0].usage if ends else None}",
    )

    # A user or tool-result message in that same array carries no `usage` and
    # must not raise or contribute zeros that mask a genuinely missing count.
    reducer = TurnReducer()
    feed(reducer, {"type": "agent_end", "messages": [{"role": "user", "content": []}]})
    check(reducer.usage == {}, f"a non-assistant message in `agent_end.messages` must be ignored, got {reducer.usage}")


def check_pricing() -> None:
    """`cost_usd` bills a known model, refuses to guess at an unknown one, and zero tokens cost zero."""
    prices = {"test/known": pricing.Price(input_usd_per_million=2.0, output_usd_per_million=10.0, recorded="2026-01-01")}

    cost = pricing.cost_usd("test/known", {"uncached_input_tokens": 1_000_000, "output_tokens": 500_000}, prices)
    check(cost == 2.0 + 5.0, f"cost must bill uncached input and output at their per-million rate, got {cost}")

    cost = pricing.cost_usd("test/unknown", {"uncached_input_tokens": 100, "output_tokens": 50}, prices)
    check(
        cost == pricing.UNREPORTED,
        f"a model with no price row must report {pricing.UNREPORTED!r}, not a guess, got {cost}",
    )

    cost = pricing.cost_usd("test/known", {"uncached_input_tokens": 0, "output_tokens": 0}, prices)
    check(cost == 0.0, f"zero tokens on a priced model must cost 0.0, not {pricing.UNREPORTED!r}, got {cost}")

    committed = pricing.load_prices()
    check(committed, "the committed prices.json must not be empty")
    for model, price in committed.items():
        check(price.input_usd_per_million > 0, f"{model}: input rate must be a positive USD/Mtok rate, got {price}")
        check(price.output_usd_per_million > 0, f"{model}: output rate must be a positive USD/Mtok rate, got {price}")
        check(price.recorded, f"{model}: `recorded` date must not be empty")


def check_agent_output() -> None:
    """The judge's transcript carries the anchor every rubric here reads."""
    rendered = render_agent_output(["thinking out loud", "the answer"])
    check("[ASSISTANT] thinking out loud" in rendered, "each assistant block is tagged")
    check(
        rendered.rstrip().endswith("[RESULT - SUCCESS] the answer"),
        f"the reply must sit after the last [RESULT - ...] tag, got {rendered!r}",
    )
    check("[RESULT - ERROR]" in render_agent_output(["boom"], is_error=True), "a failed turn is tagged ERROR")
    check(render_agent_output([]) == "[No output]", "an empty turn renders as coder_eval renders one")


def check_message_text() -> None:
    """Streamed deltas assemble once, and a repeated whole message does not double."""
    reducer = TurnReducer()
    feed(
        reducer,
        {"type": "message_update", "messageId": "m1", "assistantMessageEvent": {"type": "text", "delta": "Hel"}},
        {"type": "message_update", "messageId": "m1", "assistantMessageEvent": {"type": "text", "delta": "lo"}},
        {"type": "message_end", "messageId": "m1", "message": {"content": [{"type": "text", "text": "Hello"}]}},
    )
    check(
        reducer.assistant_texts == ["Hello"],
        f"the reply must be assembled exactly once, got {reducer.assistant_texts}",
    )

    reducer = TurnReducer()
    feed(
        reducer,
        {"type": "message_update", "messageId": "m2", "assistantMessageEvent": {"type": "thinking", "delta": "hmm"}},
    )
    check(reducer.assistant_texts == [], "thinking is not the reply")


def check_vocabulary_drift() -> None:
    """A frame type nobody knows is recorded; a routine one is not."""
    reducer = TurnReducer()
    feed(reducer, {"type": "notice", "text": "hi"}, {"type": "ready"}, {"type": "response", "command": "prompt"})
    check(reducer.unrecognized_types == set(), f"routine frames are not drift, got {reducer.unrecognized_types}")
    check(reducer.recognized == 0, "no recognized event frames were fed")

    feed(reducer, {"type": "tool_calling_v2"}, {"type": "turn_start"})
    check(reducer.unrecognized_types == {"tool_calling_v2"}, f"drift is recorded, got {reducer.unrecognized_types}")
    check(reducer.recognized == 1, "turn_start counts as a recognized event frame")


def main() -> None:
    for name, checker in sorted(globals().items()):
        if name.startswith("check_") and callable(checker):
            checker()
    print("check-omp-agent: the Omp frame reduction maps skills, tools, text and usage as the criteria expect")


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-omp-agent: {failure}", file=sys.stderr)
        sys.exit(1)
