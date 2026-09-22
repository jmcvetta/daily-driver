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
    kind = command.get("type")
    if kind == "get_available_commands":
        emit({"id": command["id"], "type": "response", "success": True,
              "data": {"commands": [{"name": "skill:deps"}]}})
    elif kind == "get_state":
        emit({"id": command["id"], "type": "response", "success": True,
              "data": {"sessionId": "fake-settle-session"}})
    elif kind == "set_model":
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


def check(condition: bool, message: str) -> None:
    """Fail the whole script on a false condition, naming what was expected."""
    if not condition:
        raise AssertionError(message)


async def run_scenario() -> None:
    """Early-stop on the first tool call; the frozen record keeps the skill."""
    from coder_eval.criteria.skill_triggered import SkillTriggeredChecker
    from coder_eval.models.criteria import SkillTriggeredCriterion
    from coder_eval.streaming.events import ToolStartEvent

    from coder_eval_omp.agent import OmpAgent, OmpAgentConfig

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


def main() -> None:
    asyncio.run(run_scenario())


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
