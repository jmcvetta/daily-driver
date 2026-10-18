#!/usr/bin/env python3
"""The acceptance test for the Omp arm's early-stop record.

`check-omp-agent.py` proves the frame reduction; this script proves what the
agent around it does with an early-stopped turn. It cannot live in that
script: it drives `coder_eval_omp.agent`, which needs the pinned `coder_eval`
install, and `make check` must not require that toolchain -- the same split
`check-omp-plugin` takes for the same reason.

THE INVARIANT

    A replicate that early-stops on `skill_triggered` cannot final-score 0 on
    that same criterion. The first paid run violated it (2026-09-16, issue
    #206): the watcher latched a pass on the in-flight `Skill` call, the turn
    aborted, the tool's `tool_execution_end` frame landed during the abort
    settle -- and the settle fed those frames to the reducer while emitting
    nothing, so the frozen trajectory the final check scores held no command at
    all and every positive row read 0 with the plugin provably loaded.

    That run's raw artifacts were not preserved and cannot be cited. This
    script is the standing evidence in their place: it reproduces the failure
    against the pre-fix agent from a script, offline.

    Here a fake `omp --mode rpc` replays exactly that: a skill read whose end
    frame arrives only after the stop. The frozen record must carry the `Skill`
    call with its parameters, and the real `SkillTriggeredChecker` must score
    that record 1.0 -- the watcher's pass and the final score cannot disagree.

THE ROLES PIN

    An arm's `model` must reach every Omp chat role in `config.yml` as
    `modelRoles`; its recognized `:level` suffix must also become a separate
    `set_thinking_level` RPC command. An arm without a model gets no
    `modelRoles` at all. Unpinned, Omp's helper roles and subagents run on
    whatever the provider catalog offers, a model the arm does not measure.
    Found while preparing the first GPT 6 Luna run (#483).

NEEDS

    The pinned `coder_eval` (for the agent base class), and nothing else. No
    real `omp` binary and no network: the fake answers the RPC handshake from
    a script. `make check` does not require the toolchain, so this is not a
    `check` leg -- the same split `check-omp-plugin` takes.
"""

from __future__ import annotations

import asyncio
import json
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals" / "coder-eval-omp" / "src"))

PROMPT = "/deps"

# The RPC a fake `omp` must speak for one early-stopped turn. `plugin link`
# succeeds silently; the handshake answers the startup reads; the prompt opens
# a turn, dispatches one skill read, and then waits for the abort an early
# stop sends before completing the tool call and the turn.
FAKE_OMP = """\
#!/usr/bin/env python3
import json
import sys


def emit(frame):
    print(json.dumps(frame), flush=True)


argv = sys.argv[1:]
if argv[:1] == ["plugin"]:
    sys.exit(0)  # `omp plugin link <root>`: succeed, install nothing

# RPC mode: ready, then answer every startup command, then run the scenario.
emit({"type": "ready"})
while True:
    line = sys.stdin.readline()
    if not line:
        break
    command = json.loads(line)
    with open(sys.argv[0] + ".commands", "a", encoding="utf-8") as log:
        log.write(json.dumps(command) + "\\n")
    kind = command.get("type")
    if kind == "get_available_commands":
        emit({"id": command["id"], "type": "response", "success": True,
              "data": {"commands": [{"name": "skill:deps"}]}})
    elif kind == "get_state":
        emit({"id": command["id"], "type": "response", "success": True,
              "data": {"sessionId": "fake-settle-session"}})
    elif kind in ("set_model", "set_thinking_level"):
        emit({"id": command["id"], "type": "response", "success": True, "data": {}})
    elif kind == "prompt":
        emit({"id": command["id"], "type": "response", "command": "prompt", "success": True})
        emit({"type": "turn_start"})
        emit({"type": "tool_execution_start", "toolCallId": "t1", "toolName": "read",
              "args": {"path": "skill://deps"}})
        # The engagement is on the wire. The watcher's live verdict latches
        # here; nothing more is emitted until the abort arrives -- the tool
        # call finishes only during the settle, which is the window the fix
        # exists for.
        follow = {}
        while True:
            follow = json.loads(sys.stdin.readline())
            if follow.get("type") == "abort":
                break
        emit({"id": follow["id"], "type": "response", "command": "abort", "success": True})
        emit({"type": "tool_execution_end", "toolCallId": "t1", "toolName": "read",
              "result": {"content": [{"type": "text", "text": "SKILL.md body"}]}})
        emit({"type": "agent_end", "isTerminal": True,
              "messages": [{"role": "assistant",
                            "usage": {"input": 22586, "output": 47, "cacheRead": 10,
                                      "cacheWrite": 0, "totalTokens": 22643}}]})
        break
"""


# A fake `omp` whose orchestrator hands its turn to background workers: a
# non-terminal `agent_end` with `awaitingAsyncWork`, then silence. It answers
# `get_subagents` with one running and one finished subagent and logs every
# command, so the check can see which ones were cancelled.
FAKE_PROMPT_BRANCH = "    elif kind == \"prompt\":"
assert FAKE_PROMPT_BRANCH in FAKE_OMP, "FAKE_OMP lost the prompt branch FAKE_OMP_ASYNC splits on"
FAKE_OMP_ASYNC = FAKE_OMP.split(FAKE_PROMPT_BRANCH)[0] + """\
    elif kind == "get_subagents":
        emit({"id": command["id"], "type": "response", "success": True,
              "data": {"subagents": [{"id": "sub-run", "status": "running"},
                                      {"id": "sub-done", "status": "completed"}]}})
    elif kind == "cancel_subagent":
        emit({"id": command["id"], "type": "response", "success": True,
              "data": {"cancelled": True}})
    elif kind == "prompt":
        emit({"id": command["id"], "type": "response", "command": "prompt", "success": True})
        emit({"type": "turn_start"})
        emit({"type": "agent_end", "isTerminal": False, "awaitingAsyncWork": True,
              "messages": [{"role": "assistant",
                            "usage": {"input": 10, "output": 5, "cacheRead": 0,
                                      "cacheWrite": 0, "totalTokens": 15}}]})
"""


# A fake `omp` whose orchestrator dispatches workers: a `task` call that starts
# with no arguments and gets them in a later update, a call the runtime rejects,
# and then either a normal end or a dead process holding a third call open.
# `.mode` picks which, so one script covers the clean and the exceptional exit.
FAKE_OMP_DISPATCH = FAKE_OMP.split(FAKE_PROMPT_BRANCH)[0] + """\
    elif kind == "prompt":
        emit({"id": command["id"], "type": "response", "command": "prompt", "success": True})
        emit({"type": "turn_start"})
        tasks = [{"id": "a", "description": "d", "task": "undertake #990009"},
                 {"id": "b", "description": "d", "task": "undertake #990011"}]
        emit({"type": "tool_execution_start", "toolCallId": "d1", "toolName": "task"})
        emit({"type": "tool_execution_update", "toolCallId": "d1", "toolName": "task",
              "args": {"agent": "implementation", "tasks": tasks[:1]}})
        emit({"type": "tool_execution_update", "toolCallId": "d1", "toolName": "task",
              "args": {"agent": "implementation", "context": "c" * 3000, "tasks": tasks}})
        text = "Spawned 2 background agents using implementation.\\n- w1\\n- w2"
        emit({"type": "tool_execution_end", "toolCallId": "d1", "toolName": "task",
              "result": {"content": [{"type": "text", "text": text}], "details": {"jobs": 2}}})
        emit({"type": "tool_execution_start", "toolCallId": "d2", "toolName": "task",
              "args": {"agent": "reasoning", "tasks": [{"task": "undertake #990010"}]}})
        emit({"type": "tool_execution_end", "toolCallId": "d2", "toolName": "task",
              "isError": True, "error": "no route for reasoning"})
        emit({"type": "tool_execution_start", "toolCallId": "d3", "toolName": "task",
              "args": {"agent": "implementation", "tasks": [{"task": "undertake #990009"}]}})
        if open(sys.argv[0] + ".mode").read() == "crash":
            sys.exit(3)  # the process dies with d3 still open
        emit({"type": "tool_execution_end", "toolCallId": "d3", "toolName": "task", "result": "nope"})
        emit({"type": "agent_end", "isTerminal": True,
              "messages": [{"role": "assistant",
                            "usage": {"input": 10, "output": 5, "cacheRead": 0,
                                      "cacheWrite": 0, "totalTokens": 15}}]})
        break
"""


# A fake `omp` driven by `<fake>.script.json`: a list with one entry per `prompt`
# command, in order. An entry's `frames` are emitted as written; its `then` is
# `silence` (keep answering commands, emit nothing more; also the default) or
# `exit` (die). `get_subagents` reports one finished and two
# running subagents, of which `sub-fail` refuses its cancel.
FAKE_OMP_SCRIPTED = """\
#!/usr/bin/env python3
import json
import sys


def emit(frame):
    print(json.dumps(frame), flush=True)


if sys.argv[1:2] == ["plugin"]:
    sys.exit(0)
SCRIPT = json.load(open(sys.argv[0] + ".script.json"))
prompts = 0
emit({"type": "ready"})
while True:
    line = sys.stdin.readline()
    if not line:
        break
    command = json.loads(line)
    with open(sys.argv[0] + ".commands", "a", encoding="utf-8") as log:
        log.write(json.dumps(command) + "\\n")
    kind = command.get("type")
    ok = {"id": command["id"], "type": "response", "success": True}
    if kind == "get_available_commands":
        emit({**ok, "data": {"commands": [{"name": "skill:deps"}]}})
    elif kind == "get_state":
        emit({**ok, "data": {"sessionId": "fake-scripted"}})
    elif kind in ("set_model", "set_thinking_level", "abort"):
        emit({**ok, "data": {}})
    elif kind == "get_subagents":
        emit({**ok, "data": {"subagents": [{"id": "sub-run", "status": "running"},
                                            {"id": "sub-fail", "status": "running"},
                                            {"id": "sub-done", "status": "completed"}]}})
    elif kind == "cancel_subagent":
        if command.get("subagentId") == "sub-fail":
            emit({"id": command["id"], "type": "response", "success": False, "error": "refused"})
        else:
            emit({**ok, "data": {"cancelled": True}})
    elif kind == "prompt":
        step = SCRIPT[min(prompts, len(SCRIPT) - 1)]
        prompts += 1
        emit({**ok, "command": "prompt"})
        for frame in step["frames"]:
            emit(frame)
        if step.get("then") == "exit":
            sys.exit(0)
"""

USAGE = {"input": 4, "output": 2, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 6}
TURN_START = {"type": "turn_start"}
SECRET = "SECRET-TOOL-ARGUMENT"


def tool_frames(call_id: str = "t1") -> list[dict[str, Any]]:
    """A completed `task` call whose arguments must never reach the diagnostic file."""
    return [
        {"type": "tool_execution_start", "toolCallId": call_id, "toolName": "task", "args": {"prompt": SECRET}},
        {"type": "tool_execution_end", "toolCallId": call_id, "toolName": "task",
         "result": {"content": [{"type": "text", "text": "spawned"}]}},
    ]


def agent_end(**fields: Any) -> dict[str, Any]:
    return {"type": "agent_end", "messages": [{"role": "assistant", "usage": USAGE}], **fields}


class EventCounter:
    """A StreamCallback that counts the terminal events and the tool dispatches."""

    def __init__(self) -> None:
        self.ends = 0
        self.tools = 0

    def on_event(self, event: Any) -> None:
        from coder_eval.streaming.events import AgentEndEvent, ToolStartEvent

        if isinstance(event, AgentEndEvent):
            self.ends += 1
        elif isinstance(event, ToolStartEvent):
            self.tools += 1


async def launch_scripted(script: list[dict[str, Any]], *, settle: bool = False, workdir: Path | None = None):
    """A started agent over the scripted fake, and the paths a check inspects."""
    from coder_eval_omp.agent import OmpAgent, OmpAgentConfig

    workdir = workdir or Path(tempfile.mkdtemp(prefix="omp-evidence-check-"))
    fake = Path(tempfile.mkdtemp(prefix="fake-omp-bin-")) / "fake-omp"
    fake.write_text(FAKE_OMP_SCRIPTED)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    Path(str(fake) + ".script.json").write_text(json.dumps(script))
    config = OmpAgentConfig(
        type="omp", binary=str(fake), plugins=[{"type": "local", "path": str(ROOT)}],
        settle_on_async_handoff=settle,
    )
    agent = OmpAgent(config, task_id="evidence-check")
    await agent.start(str(workdir))
    return agent, workdir, fake


def read_attempts(workdir: Path) -> list[dict[str, Any]]:
    from coder_eval_omp.agent import PROTOCOL_EVIDENCE_FILENAME, SETTLEMENT_EVIDENCE_VERSION

    text = (workdir / PROTOCOL_EVIDENCE_FILENAME).read_text()
    check(SECRET not in text, "the diagnostic file must not carry tool arguments")
    block = json.loads(text)["omp_settlement_evidence"]
    check(block["version"] == SETTLEMENT_EVIDENCE_VERSION, f"unexpected evidence version {block['version']}")
    return block["attempts"]


async def attempt_outcome(agent: Any, *, timeout: float, counter: EventCounter | None = None, prompt: str = "go"):
    """Run one turn and return the exception it ended in, or the record."""
    try:
        return await agent.communicate(prompt, timeout=timeout, stream_callback=counter)
    except BaseException as error:  # noqa: BLE001 - the check inspects every exit class
        return error


async def check_settlement_evidence() -> None:
    """Every exit of an attempt leaves its settlement evidence in the artifact."""
    from coder_eval.errors import AgentCrashError, TurnTimeoutError

    # A launched worker followed by silence: the timeout leaves the call and no end.
    agent, workdir, fake = await launch_scripted([{"frames": [TURN_START, *tool_frames()], "then": "silence"}])
    counter = EventCounter()
    try:
        outcome = await attempt_outcome(agent, timeout=2, counter=counter)
        check(isinstance(outcome, TurnTimeoutError), f"silence must time out, got {outcome!r}")
        check(counter.ends == 1, f"the timed-out turn must finalize exactly once, got {counter.ends}")
        check(
            agent.pending_turn is not None and len(agent.pending_turn.commands) == 1,
            "the timeout must keep the worker launch in the partial record",
        )
        (attempt,) = read_attempts(workdir)
        check(attempt["exit_reason"] == "timeout", f"exit reason must be timeout, got {attempt}")
        check(attempt["agent_end"]["total"] == 0 and attempt["agent_end"]["recent"] == [],
              f"no end was observed, got {attempt['agent_end']}")
        check(attempt["last_recognized_frame"] == "tool_execution_end" and attempt["recognized_frames"] >= 3,
              f"the last recognized frame must be kept, got {attempt}")
        check(attempt["pending_tools_at_exit"] == 0 and attempt["attempt"] == 1, f"unexpected attempt {attempt}")
        check(attempt["async_settlement"] == {"enabled": False, "taken": False}, f"async flags: {attempt}")
    finally:
        await agent.stop()

    # A non-terminal end that is not awaiting async work does not settle; flags survive.
    agent, workdir, fake = await launch_scripted(
        [{"frames": [TURN_START, agent_end(isTerminal=False, awaitingAsyncWork=False)], "then": "silence"}],
        settle=True,
    )
    try:
        outcome = await attempt_outcome(agent, timeout=2)
        check(isinstance(outcome, TurnTimeoutError), f"a plain non-terminal end must not settle, got {outcome!r}")
        (attempt,) = read_attempts(workdir)
        check(attempt["agent_end"]["nonterminal"] == 1 and attempt["agent_end"]["awaiting_async_work"] == 0,
              f"counts: {attempt['agent_end']}")
        check(attempt["agent_end"]["recent"][0]["is_terminal"] is False
              and attempt["agent_end"]["recent"][0]["awaiting_async_work"] is False,
              f"flags must survive the timeout, got {attempt['agent_end']}")
    finally:
        await agent.stop()

    # Missing fields stay distinguishable from false ones.
    agent, workdir, fake = await launch_scripted([{"frames": [TURN_START, agent_end()]}])
    try:
        await agent.communicate("go", timeout=10)
        (attempt,) = read_attempts(workdir)
        check(attempt["exit_reason"] == "completed", f"a terminal end completes the attempt, got {attempt}")
        check(attempt["agent_end"]["recent"][0]["is_terminal"] is None
              and attempt["agent_end"]["recent"][0]["awaiting_async_work"] is None,
              f"absent fields must read null, got {attempt['agent_end']}")
    finally:
        await agent.stop()

    # Async-awaiting end: opted in it settles and cancels only running workers; off it waits.
    handoff = {"frames": [TURN_START, *tool_frames(), agent_end(isTerminal=False, awaitingAsyncWork=True)],
               "then": "silence"}
    agent, workdir, fake = await launch_scripted([handoff], settle=True)
    try:
        await agent.communicate("go", timeout=10)
        cancelled = [json.loads(l).get("subagentId") for l in Path(str(fake) + ".commands").read_text().splitlines()
                     if json.loads(l).get("type") == "cancel_subagent"]
        check(cancelled == ["sub-run", "sub-fail"], f"only running workers are cancelled, got {cancelled}")
        (attempt,) = read_attempts(workdir)
        check(attempt["exit_reason"] == "async_handoff" and attempt["async_settlement"] == {"enabled": True, "taken": True},
              f"async settlement must be recorded, got {attempt}")
        check(attempt["cancellation"] == {"succeeded": 1, "failed": 1, "timed_out": 0},
              f"cancellation counts: {attempt['cancellation']}")
        check(json.loads((workdir / "omp-protocol-observations.json").read_text())["omp_cancelled_subagents"] == ["sub-run"],
              "cancelled ids stay in the artifact")
    finally:
        await agent.stop()
    agent, workdir, fake = await launch_scripted([handoff], settle=False)
    try:
        outcome = await attempt_outcome(agent, timeout=2)
        check(isinstance(outcome, TurnTimeoutError), f"with the option off the turn waits, got {outcome!r}")
        commands = [json.loads(l)["type"] for l in Path(str(fake) + ".commands").read_text().splitlines()]
        check("cancel_subagent" not in commands, "workers must not be cancelled with the option off")
        (attempt,) = read_attempts(workdir)
        check(attempt["agent_end"]["awaiting_async_work"] == 1
              and attempt["agent_end"]["recent"][0]["awaiting_async_work"] is True
              and attempt["async_settlement"] == {"enabled": False, "taken": False},
              f"the observation must survive the timeout, got {attempt}")
    finally:
        await agent.stop()

    # Provider failure and EOF keep their failure class and their observations.
    refused = json.loads((ROOT / "evals" / "coder-eval-omp" / "fixtures" / "agent_end_provider_error.json").read_text())
    for name, step, reason in (
        ("provider failure", {"frames": [TURN_START, {"type": "agent_end", **refused}]}, "provider_error"),
        ("EOF", {"frames": [TURN_START, *tool_frames()], "then": "exit"}, "eof"),
    ):
        agent, workdir, fake = await launch_scripted([step])
        counter = EventCounter()
        try:
            outcome = await attempt_outcome(agent, timeout=10, counter=counter)
            check(isinstance(outcome, AgentCrashError), f"{name} must stay an AgentCrashError, got {outcome!r}")
            check(counter.ends == 1, f"{name} must finalize exactly once, got {counter.ends}")
            (attempt,) = read_attempts(workdir)
            check(attempt["exit_reason"] == reason, f"{name} exit reason, got {attempt}")
        finally:
            await agent.stop()

    # External cancellation.
    agent, workdir, fake = await launch_scripted([{"frames": [TURN_START, *tool_frames()], "then": "silence"}])
    counter = EventCounter()
    try:
        task = asyncio.ensure_future(attempt_outcome(agent, timeout=60, counter=counter))
        for _ in range(100):
            if counter.tools:
                break
            await asyncio.sleep(0.1)
        check(counter.tools == 1, "the scripted tool call must have been dispatched before the cancel")
        await asyncio.sleep(0.3)
        task.cancel()
        outcome = await asyncio.gather(task, return_exceptions=True)
        check(isinstance(outcome[0], asyncio.CancelledError), f"cancellation must propagate, got {outcome!r}")
        check(counter.ends == 1, f"a cancelled turn must finalize exactly once, got {counter.ends}")
        (attempt,) = read_attempts(workdir)
        check(attempt["exit_reason"] == "cancelled", f"cancel exit reason, got {attempt}")
    finally:
        await agent.stop()

    # A second attempt keeps the first's record and starts with fresh flags; the
    # retained agent_end observations are bounded with the overflow counted.
    agent, workdir, fake = await launch_scripted([
        {"frames": [TURN_START, agent_end(isTerminal=False, awaitingAsyncWork=False)], "then": "silence"},
        {"frames": [TURN_START, *[agent_end(isTerminal=False) for _ in range(20)], agent_end(isTerminal=True)]},
    ])
    try:
        first = await attempt_outcome(agent, timeout=2)
        check(isinstance(first, TurnTimeoutError), f"the first attempt times out, got {first!r}")
        await agent.discard_pending_turn()
        await agent.communicate("again", timeout=10)
        first_attempt, second = read_attempts(workdir)
        check(first_attempt["exit_reason"] == "timeout" and first_attempt["agent_end"]["nonterminal"] == 1,
              f"the first attempt record must survive a later attempt, got {first_attempt}")
        check(second["attempt"] == 2 and second["exit_reason"] == "completed", f"second attempt: {second}")
        ends = second["agent_end"]
        check(ends["total"] == 21 and ends["nonterminal"] == 20 and ends["terminal"] == 1,
              f"second attempt must not reuse earlier flags, got {ends}")
        check(len(ends["recent"]) == 16 and ends["overflow"] == 5, f"bounded retention, got {ends['overflow']}")
    finally:
        await agent.stop()

    # An evidence write that fails must not mask a timeout, and must not hide itself on success.
    for script, expected, name in (
        ([{"frames": [TURN_START, *tool_frames()], "then": "silence"}], TurnTimeoutError, "timeout"),
        ([{"frames": [TURN_START, agent_end()]}], AgentCrashError, "normal completion"),
    ):
        blocked = Path(tempfile.mkdtemp(prefix="omp-evidence-blocked-"))
        (blocked / "omp-protocol-observations.json").mkdir()
        agent, _, _ = await launch_scripted(script, workdir=blocked)
        try:
            outcome = await attempt_outcome(agent, timeout=2)
            check(isinstance(outcome, expected), f"a failed write on {name} must end as {expected.__name__}, got {outcome!r}")
        finally:
            await agent.stop()

    print("check-omp-agent-settle: every exit of an attempt (timeout, async handoff, provider failure, EOF, "
          "cancellation, retry) leaves bounded settlement evidence; a failed write masks nothing")

def check(condition: bool, message: str) -> None:
    """Fail the whole script on a false condition, naming what was expected."""
    if not condition:
        raise AssertionError(message)


async def run_scenario() -> None:
    """Early-stop on the first tool call; the frozen record keeps the skill."""
    from coder_eval.criteria.skill_triggered import SkillTriggeredChecker
    from coder_eval.models.criteria import SkillTriggeredCriterion
    from coder_eval.streaming.events import ToolStartEvent

    from coder_eval_omp.agent import OmpAgent, OmpAgentConfig, PROTOCOL_EVIDENCE_FILENAME

    class ToolStartCounter:
        """A StreamCallback that counts tool dispatches, like the watcher does."""

        def __init__(self) -> None:
            self.n = 0

        def on_event(self, event: Any) -> None:
            if isinstance(event, ToolStartEvent):
                self.n += 1

    workdir = Path(tempfile.mkdtemp(prefix="omp-settle-check-"))
    bindir = Path(tempfile.mkdtemp(prefix="fake-omp-bin-"))
    fake = bindir / "fake-omp"
    fake.write_text(FAKE_OMP)
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)

    config = OmpAgentConfig(
        type="omp",
        model="google-antigravity/gemini-3.8-flash:high",
        binary=str(fake),
        plugins=[{"type": "local", "path": str(ROOT)}],
    )
    agent = OmpAgent(config, task_id="settle-check")
    await agent.start(str(workdir))

    counter = ToolStartCounter()

    def should_stop() -> bool:
        # The EarlyStopWatcher's shape, reduced to its load-bearing line: a
        # tool call was dispatched, so a pass-latched trigger has fired.
        return counter.n > 0

    try:
        record = await agent.communicate(
            PROMPT,
            timeout=30,
            should_stop=should_stop,
            stream_callback=counter,
        )
    finally:
        await agent.stop()

    wire_commands = [
        {key: value for key, value in command.items() if key != "id"}
        for command in (json.loads(line) for line in Path(str(fake) + ".commands").read_text().splitlines())
        if command.get("type") in ("set_model", "set_thinking_level")
    ]
    check(
        wire_commands
        == [
            {
                "type": "set_model",
                "provider": "google-antigravity",
                "modelId": "gemini-3.8-flash",
            },
            {"type": "set_thinking_level", "level": "high"},
        ],
        f"the task selector must reach RPC as model and thinking commands, got {wire_commands}",
    )

    observed = json.loads((workdir / PROTOCOL_EVIDENCE_FILENAME).read_text())
    check(
        {key: observed[key] for key in ("omp_argument_keys_seen", "omp_usage_keys_seen")}
        == {
            "omp_argument_keys_seen": ["args"],
            "omp_usage_keys_seen": ["cacheRead", "cacheWrite", "input", "output"],
        },
        "post-turn protocol evidence must contain the exact observed key union",
    )
    check(
        [a["exit_reason"] for a in observed["omp_settlement_evidence"]["attempts"]] == ["stopped_early"],
        f"an early stop must be recorded as its own exit reason, got {observed['omp_settlement_evidence']}",
    )

    check(
        counter.n == 1,
        f"the scripted turn dispatches exactly one tool call, got {counter.n}",
    )
    check(
        len(record.commands) == 1 and record.commands[0].tool_name == "Skill",
        f"the frozen record must carry the Skill call the stop latched on, got "
        f"{[(c.tool_name, c.parameters) for c in record.commands]}",
    )
    check(
        record.commands[0].parameters == {"skill": "deps"},
        f"the skill call must keep its parameters, got {record.commands[0].parameters}",
    )

    # The invariant the replacement dispatch's terms named: a run that
    # early-stops on a criterion's pass cannot final-score 0 on that same
    # criterion. The watcher's pass and the checker's frozen trajectory must
    # agree, so the real checker scores the real frozen record.
    checker = SkillTriggeredChecker()
    result = checker._check_impl(
        SkillTriggeredCriterion(
            description="`deps` fires on the literal /deps",
            skill_name="deps",
            expected_skill="deps",
        ),
        None,  # type: ignore[arg-type]  (skill_triggered reads the trajectory, never the sandbox)
        turn_records=[record],
    )
    check(
        result.score == 1.0 and result.observed_label == "yes",
        f"early-stop-on-pass must not final-score 0 on the same criterion, got {result.score} "
        f"({result.details})",
    )
    print(
        "check-omp-agent-settle: an early-stopped turn keeps the tool call the stop latched on; "
        "skill_triggered scores the frozen record 1.0"
    )


FAKE_OMP_REFUSED = """\
#!/usr/bin/env python3
import json
import sys

REFUSED = json.load(open(sys.argv[0] + ".refused.json"))
OK = {"role": "assistant", "content": [{"type": "text", "text": "ok"}], "stopReason": "stop",
      "usage": {"input": 5, "output": 1, "cacheRead": 0, "cacheWrite": 0, "totalTokens": 6}}


def emit(frame):
    print(json.dumps(frame), flush=True)


if sys.argv[1:2] == ["plugin"]:
    sys.exit(0)
emit({"type": "ready"})
refuse = open(sys.argv[0] + ".mode").read() == "refuse"
while True:
    line = sys.stdin.readline()
    if not line:
        break
    command = json.loads(line)
    kind = command.get("type")
    if kind == "get_available_commands":
        emit({"id": command["id"], "type": "response", "success": True, "data": {"commands": []}})
    elif kind == "get_state":
        emit({"id": command["id"], "type": "response", "success": True, "data": {"sessionId": "fake"}})
    elif kind in ("set_model", "set_thinking_level"):
        emit({"id": command["id"], "type": "response", "success": True, "data": {}})
    elif kind == "prompt":
        emit({"id": command["id"], "type": "response", "command": "prompt", "success": True})
        emit({"type": "turn_start"})
        messages = REFUSED["messages"] if refuse else [OK]
        emit({"type": "message_end", "message": messages[-1]})
        emit({"type": "agent_end", "isTerminal": True, "messages": messages})
        break
"""


async def run_provider_error_scenario() -> None:
    """A refused provider call ends the attempt as a crash; a normal turn does not."""
    from coder_eval.errors import AgentCrashError

    from coder_eval_omp.agent import OmpAgent, OmpAgentConfig

    refused = ROOT / "evals" / "coder-eval-omp" / "fixtures" / "agent_end_provider_error.json"
    message = json.loads(refused.read_text())["messages"][1]["errorMessage"]
    for name, refuse in (("REFUSE", True), ("PLAIN", False)):
        workdir = Path(tempfile.mkdtemp(prefix="omp-refused-check-"))
        fake = Path(tempfile.mkdtemp(prefix="fake-omp-bin-")) / f"fake-omp-{name}"
        fake.write_text(FAKE_OMP_REFUSED)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        Path(str(fake) + ".refused.json").write_text(refused.read_text())
        Path(str(fake) + ".mode").write_text("refuse" if refuse else "plain")
        agent = OmpAgent(OmpAgentConfig(type="omp", binary=str(fake)), task_id="refused-check")
        await agent.start(str(workdir))
        try:
            if refuse:
                try:
                    await agent.communicate("hi", timeout=30)
                except AgentCrashError as crash:
                    check(message in str(crash), f"the crash must carry the provider message, got {crash}")
                else:
                    check(False, "a refused provider call must end the attempt as AgentCrashError")
            else:
                record = await agent.communicate("hi", timeout=30)
                check(record is not None, "a normal completed turn must still settle")
        finally:
            await agent.stop()
    print("check-omp-agent-settle: a refused provider call crashes the attempt with its message; a normal turn does not")


async def check_dispatch_evidence() -> None:
    """`record_task_dispatches` keeps every attempted task call, even through a crash."""
    from coder_eval.errors import AgentCrashError
    from coder_eval_omp.agent import DISPATCH_EVIDENCE_FILENAME, OmpAgent, OmpAgentConfig

    async def run(mode: str, record: bool = True) -> Path:
        workdir = Path(tempfile.mkdtemp(prefix="omp-dispatch-check-"))
        fake = Path(tempfile.mkdtemp(prefix="fake-omp-bin-")) / f"fake-omp-{mode}"
        fake.write_text(FAKE_OMP_DISPATCH)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        Path(str(fake) + ".mode").write_text(mode)
        config = OmpAgentConfig(
            type="omp", binary=str(fake), plugins=[{"type": "local", "path": str(ROOT)}],
            record_task_dispatches=record,
        )
        agent = OmpAgent(config, task_id="dispatch-check")
        await agent.start(str(workdir))
        try:
            await agent.communicate("dispatch", timeout=30)
        except AgentCrashError:
            check(mode == "crash", "only the crashing scenario may crash")
        finally:
            await agent.stop()
        return workdir / DISPATCH_EVIDENCE_FILENAME

    for mode in ("clean", "crash"):
        document = json.loads((await run(mode)).read_text())
        check(document["version"] == 1 and document["complete"] is True, f"{mode}: versioned, complete document")
        calls = document["calls"]
        check([c["call_id"] for c in calls] == ["d1", "d2", "d3"], f"{mode}: every attempted call is kept, got {calls}")
        first = calls[0]
        check([t["task"] for t in first["arguments"]["tasks"]] == ["undertake #990009", "undertake #990011"],
              f"{mode}: the final argument update wins")
        check(len(first["arguments"]["context"]) == 3000, f"{mode}: no field is truncated")
        check(first["result"]["details"] == {"jobs": 2} and first["status"] == "ok", f"{mode}: raw result kept")
        check(calls[1]["status"] == "error", f"{mode}: the rejected call is kept")
        check(calls[2]["status"] == ("ok" if mode == "clean" else "unresolved"), f"{mode}: the open call's outcome")
        check(all(c["attempt"] == 1 for c in calls), f"{mode}: attempt identity")
    off = await run("clean", record=False)
    check(not off.exists(), "the artifact is opt-in; off writes nothing")
    print("check-omp-agent-settle: task dispatches are kept whole, rejected and unresolved ones included, "
          "through a normal end and a crash; off writes nothing")


def check_failed_dispatch_rewrite() -> None:
    """A failed rewrite must not let the grader reuse a previous complete artifact."""
    from unittest.mock import patch

    from coder_eval_omp.agent import DISPATCH_EVIDENCE_FILENAME, OmpAgent, OmpAgentConfig
    from coder_eval_omp.rpc import TurnReducer

    workdir = Path(tempfile.mkdtemp(prefix="omp-dispatch-write-failure-"))
    destination = workdir / DISPATCH_EVIDENCE_FILENAME
    destination.write_text('{"version":1,"complete":true,"calls":[]}', encoding="utf-8")
    agent = OmpAgent(OmpAgentConfig(type="omp", record_task_dispatches=True))
    agent.working_directory = str(workdir)
    with patch.object(Path, "write_text", side_effect=OSError("injected write failure")):
        agent._record_task_dispatches(TurnReducer(), attempt=2, iteration=1)
    check(not destination.exists(), "a failed rewrite removes prior passing evidence")
    print("check-omp-agent-settle: failed dispatch rewrite removes stale evidence")


def check_roles_pin() -> None:
    """The arm's `model` pins every Omp chat role in config.yml, and only then."""
    import yaml

    from coder_eval_omp.agent import OMP_CHAT_ROLES, OmpAgent, OmpAgentConfig

    model = "google-antigravity/gemini-3.8-flash:high"
    check("memory" in OMP_CHAT_ROLES and "task" in OMP_CHAT_ROLES, f"chat roles incomplete: {OMP_CHAT_ROLES}")
    for given, expected in ((model, {role: model for role in OMP_CHAT_ROLES}), (None, None)):
        home = Path(tempfile.mkdtemp(prefix="omp-roles-check-"))
        agent = OmpAgent(OmpAgentConfig(type="omp", model=given), task_id="roles-check")
        agent._prepare_home(home)
        written = yaml.safe_load((home / ".omp" / "agent" / "config.yml").read_text())
        check(
            written.get("skills") == {"enableSkillCommands": True},
            f"config.yml must keep skill commands on, got {written}",
        )
        check(written.get("fetch") == {"enabled": False}, f"config.yml must keep fetch off, got {written}")
        check(
            written.get("modelRoles") == expected,
            f"model {given} must write modelRoles {expected}, got {written.get('modelRoles')}",
        )
    print("check-omp-agent-settle: the arm's model pins every Omp chat role, and no model pins none")


async def check_async_handoff() -> None:
    """`settle_on_async_handoff` settles on a non-terminal, async-awaiting end."""
    from coder_eval.errors import TurnTimeoutError
    from coder_eval_omp.agent import OmpAgent, OmpAgentConfig, PROTOCOL_EVIDENCE_FILENAME

    async def run(enabled: bool, timeout: float):
        workdir = Path(tempfile.mkdtemp(prefix="omp-async-check-"))
        bindir = Path(tempfile.mkdtemp(prefix="fake-omp-bin-"))
        fake = bindir / "fake-omp"
        fake.write_text(FAKE_OMP_ASYNC)
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
        config = OmpAgentConfig(
            type="omp", binary=str(fake), plugins=[{"type": "local", "path": str(ROOT)}],
            settle_on_async_handoff=enabled,
        )
        agent = OmpAgent(config, task_id="async-check")
        await agent.start(str(workdir))
        try:
            record = await agent.communicate("dispatch", timeout=timeout)
        finally:
            await agent.stop()
        commands = [json.loads(l) for l in Path(str(fake) + ".commands").read_text().splitlines()]
        return workdir, record, commands

    workdir, record, commands = await run(True, 30)
    cancelled = [c["subagentId"] for c in commands if c.get("type") == "cancel_subagent"]
    check(cancelled == ["sub-run"], f"only the running subagent is cancelled, got {cancelled}")
    check(record is not None, "the turn must settle with a record")
    evidence = json.loads((workdir / PROTOCOL_EVIDENCE_FILENAME).read_text())
    check(
        evidence.get("omp_cancelled_subagents") == ["sub-run"],
        f"cancelled ids must be recorded in the protocol evidence, got {evidence}",
    )

    try:
        _, _, commands = await run(False, 2)
    except TurnTimeoutError:  # the turn times out instead of settling
        pass
    else:
        raise AssertionError("with the setting off, the turn must not settle on a non-terminal end")
    print("check-omp-agent-settle: settle_on_async_handoff settles on the async handoff and cancels "
          "running subagents; off, the turn keeps waiting")


def main() -> None:
    asyncio.run(run_scenario())
    asyncio.run(check_async_handoff())
    asyncio.run(check_dispatch_evidence())
    check_failed_dispatch_rewrite()
    asyncio.run(run_provider_error_scenario())
    asyncio.run(check_settlement_evidence())
    check_roles_pin()

if __name__ == "__main__":
    try:
        main()
    except ImportError as error:
        # The Makefile target pins `coder-eval` into the environment, so
        # reaching this branch means a broken install — a failure of the
        # check's own prerequisite, not a skip. Say so and fail.
        print(f"check-omp-agent-settle: FAILED - this check needs the pinned coder_eval install: {error}",
              file=sys.stderr)
        print("rebuild it with `make evals-install`", file=sys.stderr)
        sys.exit(1)
    except AssertionError as failure:
        print(f"check-omp-agent-settle: {failure}", file=sys.stderr)
        sys.exit(1)
