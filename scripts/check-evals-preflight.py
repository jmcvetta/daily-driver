#!/usr/bin/env python3
"""Assert the eval preflight rejects metered judges without probing credentials.

The critical regression is a configured `ANTHROPIC_API_KEY` or Bedrock route
making `llm_judge` pass: that would permit metered Anthropic access and send an
Omp caller down a credential-troubleshooting path. The test drives the real
preflight with synthetic task YAML and no `coder-eval` executable on PATH.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "evals-preflight.py"

JUDGE_TASK = """\
task_id: fixture-judge-task
success_criteria:
  - type: llm_judge
    description: a graded finding
    prompt: does it work
"""

DISABLED_JUDGE_TASK = """\
task_id: fixture-disabled-judge-task
success_criteria:
  - type: llm_judge
    description: a disabled finding
    prompt: does it work
    enabled: false
"""

NON_JUDGE_TASK = """\
task_id: fixture-non-judge-task
success_criteria:
  - type: command_executed
    description: a command ran
    command: echo hi
"""


class Failed(Exception):
    """A regression case did not hold."""


def run(directory: Path, name: str, content: str, **overrides: str) -> subprocess.CompletedProcess[str]:
    """Run the actual preflight against one task file in a clean directory."""
    (directory / name).write_text(content, encoding="utf-8")
    env = {"PATH": "/usr/bin:/bin", "HOME": str(directory)}
    env.update(overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT), name],
        capture_output=True,
        text=True,
        cwd=directory,
        env=env,
        check=False,
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)

        # A configured API key or Bedrock route must not authorize a metered judge.
        result = run(
            directory,
            "judge.yaml",
            JUDGE_TASK,
            ANTHROPIC_API_KEY="fixture-key-not-used",
            API_BACKEND="bedrock",
            AWS_BEARER_TOKEN_BEDROCK="fixture-token-not-used",
        )
        require(result.returncode == 1, f"enabled llm_judge passed:\n{result.stdout}\n{result.stderr}")
        require("fixture-judge-task" in result.stderr, f"failure omitted task id:\n{result.stderr}")
        require("metered Anthropic API" in result.stderr, f"failure omitted safety boundary:\n{result.stderr}")
        require("Claude Code web or CLI session" in result.stderr, f"failure omitted supported route:\n{result.stderr}")
        require("ANTHROPIC_API_KEY set" not in result.stderr, f"failure recommends an API key:\n{result.stderr}")
        require("could not ask coder_eval" not in result.stderr, f"preflight probed external route:\n{result.stderr}")

        # Disabled judges remain inert, even without coder-eval on PATH.
        result = run(directory, "disabled.yaml", DISABLED_JUDGE_TASK)
        require(result.returncode == 0, f"disabled judge failed:\n{result.stdout}\n{result.stderr}")

        # Ordinary non-judge tasks require no credentials or route probe.
        result = run(directory, "plain.yaml", NON_JUDGE_TASK)
        require(result.returncode == 0, f"non-judge task failed:\n{result.stdout}\n{result.stderr}")

        # Malformed task input fails closed rather than silently skipping checks.
        result = run(directory, "bad.yaml", "success_criteria: [\n")
        require(result.returncode == 1, f"invalid YAML passed:\n{result.stdout}\n{result.stderr}")
        require("invalid YAML" in result.stderr, f"invalid YAML error missing:\n{result.stderr}")

    print("evals-preflight refuses metered judges without credential probes; 4 case(s) checked")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failed as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
