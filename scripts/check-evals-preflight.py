#!/usr/bin/env python3
"""The acceptance test for `scripts/evals-preflight.py`.

The constitution carries the rule *code without tests is broken*, and a
pre-run guard is exactly the kind of script that rule is aimed at: it runs
once, right before real money gets spent, and a guard that silently stopped
guarding would look identical to one still doing its job.

This drives the real script — the actual file, as a subprocess, with a
controlled environment — against synthetic task YAML written into a
`tempfile.TemporaryDirectory()`. No model, no credentials, no network, and no
real `coder-eval`: the guard now delegates its transport question to a probe
run under `coder-eval`'s own interpreter (see the script's module docstring),
so this test builds a STUB `coder-eval` — a fake console script with a real
shebang, and a fake `coder_eval` package on its `PYTHONPATH` exposing just
enough of `Settings`, `resolve_route`, and `DirectRoute` for the probe to
import and run — rather than depending on the real tool being installed.
That exercises the real probe code path (subprocess, shebang parsing, result
parsing) against a controlled double, so every case here belongs in `make
check` and in a CI that holds no `ANTHROPIC_API_KEY` and no `coder-eval`.

WHAT IT COVERS

    - A row with an enabled `llm_judge`, probed against a stub that reports a
      usable transport, passes.
    - The same row, probed against a stub that reports no transport, fails —
      and the failure message names the offending row's `task_id`.
    - A row with only non-judge criteria passes with no stub on `PATH` at
      all, proving the probe is never invoked when no judge row is present.
    - A row whose `llm_judge` is `enabled: false` passes the same way, probe
      never invoked.
    - `coder-eval` absent from `PATH` while a judge row IS present fails,
      with a message saying the probe could not be run.
    - The failure message names both `API_BACKEND=bedrock` and
      `ANTHROPIC_API_KEY`, guarding the PR #166 review finding that the old
      remedy text named a flag (`--backend bedrock`) that does not work
      through `make evals-run`.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "evals-preflight.py"

# A minimal but real success_criteria shape for each case. `task_id` is what
# the failure message is expected to name.
JUDGE_TASK = """\
task_id: fixture-judge-task
success_criteria:
  - type: skill_triggered
    expected_skill: some-skill
    skill_name: some-skill
  - type: llm_judge
    description: a graded finding
    prompt: does it work
"""

DISABLED_JUDGE_TASK = """\
task_id: fixture-disabled-judge-task
success_criteria:
  - type: llm_judge
    description: a graded finding, turned off
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

# The stub `coder_eval` package the probe imports. Exposes exactly the three
# names `scripts/evals-preflight.py`'s probe uses -- `Settings`,
# `resolve_route`, `DirectRoute` -- with `resolve_route` reading a transport
# flag from the environment instead of doing any real settings resolution.
# `JUDGE_TRANSPORT_STUB` controls what it reports: unset or empty means "no
# transport", any other value means "transport available". This is what lets
# each case below choose the probe's answer without touching real
# `coder_eval` internals.
STUB_CODER_EVAL_PACKAGE = """\
import os


class Settings:
    def __init__(self):
        pass


class DirectRoute:
    def __init__(self, judge_transport):
        self.judge_transport = judge_transport


def resolve_route(settings):
    if os.environ.get("JUDGE_TRANSPORT_STUB"):
        return DirectRoute(judge_transport="anthropic")
    return DirectRoute(judge_transport=None)
"""

STUB_CODER_EVAL_MODELS_PACKAGE = """\
from coder_eval_stub_impl import DirectRoute, resolve_route

__all__ = ["DirectRoute", "resolve_route"]
"""

STUB_CODER_EVAL_CONFIG_MODULE = """\
from coder_eval_stub_impl import Settings

__all__ = ["Settings"]
"""


class Failed(Exception):
    """A case that did not hold. The message is the report."""


def build_stub_coder_eval(tmpdir: Path, *, interpreter: str) -> Path:
    """Build a fake `coder-eval` on a directory of its own and return that
    directory, meant to be put first on `PATH`.

    The fake console script's shebang names `interpreter` (the real
    `sys.executable` running this test), so `find_coder_eval_interpreter` in
    the guard has a real, readable shebang line to parse — exactly the shape
    a `uv tool install` console script has, without needing one installed.

    The stub `coder_eval` package it exposes lives in a sibling `pylib`
    directory; `base_env` below puts that directory on `PYTHONPATH` for the
    guard process, and the guard's own probe subprocess inherits its
    environment (it passes no explicit `env=`), so the stub package reaches
    the probe without this test needing to touch the guard's internals.
    """
    bin_dir = tmpdir / "bin"
    bin_dir.mkdir()
    pylib_dir = tmpdir / "pylib"
    pylib_dir.mkdir()
    (pylib_dir / "coder_eval_stub_impl.py").write_text(STUB_CODER_EVAL_PACKAGE, encoding="utf-8")
    config_dir = pylib_dir / "coder_eval"
    config_dir.mkdir()
    (config_dir / "__init__.py").write_text("", encoding="utf-8")
    (config_dir / "config.py").write_text(STUB_CODER_EVAL_CONFIG_MODULE, encoding="utf-8")
    (config_dir / "models.py").write_text(STUB_CODER_EVAL_MODELS_PACKAGE, encoding="utf-8")

    # A real console script only needs to exist and be executable for
    # `find_coder_eval_interpreter` to find and parse it -- the probe never
    # actually runs THIS file, only the interpreter its shebang names, so its
    # body is irrelevant. What matters is the shebang line.
    coder_eval_script = bin_dir / "coder-eval"
    coder_eval_script.write_text(f"#!{interpreter}\nraise SystemExit('not meant to run directly')\n", encoding="utf-8")
    coder_eval_script.chmod(0o755)
    return bin_dir


def run(
    tmpdir: Path,
    files: dict[str, str],
    *,
    env: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    """Write `files` into `tmpdir`, then run the guard against their names."""
    for name, content in files.items():
        (tmpdir / name).write_text(content, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), *files],
        capture_output=True,
        text=True,
        cwd=tmpdir,
        env=env,
    )


def base_env(tmp_home: Path, *, stub_bin: Path | None, pylib_dir: Path, **overrides: str) -> dict[str, str]:
    """A minimal environment for one case.

    `PATH` carries the stub `coder-eval` first when `stub_bin` is given, and
    no `coder-eval` at all otherwise -- proving the "probe never invoked" and
    "coder-eval absent" cases actually exercise what they claim to.
    `PYTHONPATH` makes the stub `coder_eval` package importable for the
    probe subprocess the guard launches, without polluting the test
    process's own imports. `HOME` is redirected to an empty directory so a
    real developer `.env` or credential file elsewhere on the machine cannot
    leak in.

    That redirect also hides a user-site PyYAML from the guard subprocess --
    `site` resolves the user directory from `HOME` at import time -- so the
    caller's `PYTHONPATH` is carried through, after the stub's directory:
    when the leg runs under `make`, that inheritance is what brings the
    Makefile's `.dev-deps/` (and PyYAML with it) into the subprocess. The
    stub's directory stays first, so the stub `coder_eval` package still
    wins over anything on the inherited path.
    """
    path = f"{stub_bin}:/usr/bin:/bin" if stub_bin is not None else "/usr/bin:/bin"
    inherited = os.environ.get("PYTHONPATH")
    pythonpath = f"{pylib_dir}{os.pathsep}{inherited}" if inherited else str(pylib_dir)
    env = {"PATH": path, "HOME": str(tmp_home), "PYTHONPATH": pythonpath}
    env.update(overrides)
    return env


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Failed(message)


def main() -> int:
    errors: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        home = tmpdir / "home"
        home.mkdir()
        workdir = tmpdir / "work"
        workdir.mkdir()
        stub_dir = tmpdir / "stub"
        stub_dir.mkdir()
        stub_bin = build_stub_coder_eval(stub_dir, interpreter=sys.executable)
        pylib_dir = stub_dir / "pylib"

        # 1. llm_judge row, stub reports a transport -> passes.
        result = run(
            workdir,
            {"judge.yaml": JUDGE_TASK},
            env=base_env(home, stub_bin=stub_bin, pylib_dir=pylib_dir, JUDGE_TRANSPORT_STUB="1"),
        )
        if result.returncode != 0:
            errors.append(
                "case 1 (llm_judge, stub reports a transport): expected exit "
                f"0, got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
            )

        # 2. same row, stub reports no transport -> fails, names the row.
        result = run(
            workdir,
            {"judge.yaml": JUDGE_TASK},
            env=base_env(home, stub_bin=stub_bin, pylib_dir=pylib_dir),
        )
        if result.returncode != 1:
            errors.append(
                "case 2 (llm_judge, stub reports no transport): expected "
                f"exit 1, got {result.returncode}\nstderr: {result.stderr}"
            )
        if "fixture-judge-task" not in result.stderr:
            errors.append(
                "case 2: failure message does not name the offending row's "
                f"task_id ('fixture-judge-task')\nstderr: {result.stderr}"
            )
        if "API_BACKEND=bedrock" not in result.stderr:
            errors.append(
                "case 2: failure message does not name `API_BACKEND=bedrock` "
                f"as a working remedy\nstderr: {result.stderr}"
            )
        if "ANTHROPIC_API_KEY" not in result.stderr:
            errors.append(
                "case 2: failure message does not name `ANTHROPIC_API_KEY`"
                f" as a remedy\nstderr: {result.stderr}"
            )

        # 3. only non-judge criteria, no coder-eval anywhere on PATH ->
        #    passes, proving the probe is never invoked.
        result = run(
            workdir,
            {"plain.yaml": NON_JUDGE_TASK},
            env=base_env(home, stub_bin=None, pylib_dir=pylib_dir),
        )
        if result.returncode != 0:
            errors.append(
                "case 3 (no llm_judge criterion, no coder-eval on PATH): "
                f"expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
            )

        # 4. llm_judge with enabled: false, no coder-eval on PATH -> passes,
        #    probe not invoked.
        result = run(
            workdir,
            {"disabled.yaml": DISABLED_JUDGE_TASK},
            env=base_env(home, stub_bin=None, pylib_dir=pylib_dir),
        )
        if result.returncode != 0:
            errors.append(
                "case 4 (llm_judge enabled: false, no coder-eval on PATH): "
                f"expected exit 0, got {result.returncode}\nstderr: {result.stderr}"
            )

        # 5. llm_judge row present, coder-eval absent from PATH entirely ->
        #    fails, message says the probe could not run.
        result = run(
            workdir,
            {"judge.yaml": JUDGE_TASK},
            env=base_env(home, stub_bin=None, pylib_dir=pylib_dir),
        )
        if result.returncode != 1:
            errors.append(
                "case 5 (llm_judge, coder-eval absent): expected exit 1, got "
                f"{result.returncode}\nstderr: {result.stderr}"
            )
        if "coder-eval" not in result.stderr:
            errors.append(
                "case 5: failure message does not say the probe could not "
                f"be run (no mention of coder-eval)\nstderr: {result.stderr}"
            )

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print("evals-preflight guard behaves correctly; 5 case(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
