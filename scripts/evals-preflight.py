#!/usr/bin/env python3
"""Refuse to start an eval run whose `llm_judge` criteria cannot execute.

`coder_eval`'s `llm_judge` criterion needs a judge transport that is separate
from whatever authenticates the agent under test. On the default DIRECT
backend, `models/routing.py::_resolve_direct_judge_transport` picks the
transport "anthropic" iff `ANTHROPIC_API_KEY` is set, and `None` otherwise.
When it is `None`, `criteria/llm_judge.py` does not fail the run — it returns
score 0.0 with `details="(judge transport unconfigured)"`, logs one ERROR
line, and the run **continues**. The BEDROCK and LITELLM backends always have
a usable judge transport; only DIRECT can be unconfigured this way.

That "continues" is the defect this guards against. Running
`tasks/session-title/07-get-session-before-set.yaml` in a container with no
`ANTHROPIC_API_KEY` produced an `experiment.md` reading `Score 0.000 (bare) /
0.333 (with-plugin)`, `Best: with-plugin`, `Win Rates — with-plugin: 1/1 tasks
(100%)`. That reads as a clean ablation. The entire 0.333 was the weight-1
`skill_triggered` criterion; the weight-2 `llm_judge` — the one carrying the
actual finding — never ran. Nothing in the report says so: the per-replicate
log carries `API routing: anthropic_direct (judge transport: none)` and the
ERROR line, and `task.json` records `environment_info["judge_transport"]`,
but neither reaches the report a reader actually looks at. Eight of the nine
`references`-tagged rows in this suite carry their finding in a weight-2
`llm_judge`, so this one missing key silently voids most of that suite.
See docs/notes/0012-the-judge-needs-its-own-transport.md for why the fix is a
pre-run guard rather than reading the report more carefully after the fact,
and for why the guard asks `coder_eval` directly instead of mirroring its
resolution rule (an earlier version of this script did mirror it, and a
review found three ways the mirror was wrong).

HOW IT DECIDES

    This script does not know, and does not try to know, how `coder_eval`
    resolves `API_BACKEND` or `ANTHROPIC_API_KEY` — which environment
    variables, which `.env` file, which precedence between them. Asking that
    question here is what went wrong the first time: `coder_eval`'s
    `Settings` also reads a cwd-relative `.env` (`config.py`'s
    `SettingsConfigDict(env_file=".env", ...)`), and a copy of that rule in
    this repository can drift from it, or simply be built on an interpreter
    that cannot import the `python-dotenv` the real resolution depends on.

    So instead this script finds the actual `coder_eval` installation —
    `coder-eval` on `PATH`, whose shebang names its own venv's Python — and
    runs a short probe under THAT interpreter, in the current working
    directory. The probe imports `coder_eval.config.Settings` and
    `coder_eval.models.routing.resolve_route`, builds the route exactly as a
    real run would, and reports whether `criteria/llm_judge.py` would find a
    transport on it — using the same condition that module checks:
    `route is None or (isinstance(route, DirectRoute) and
    route.judge_transport is None)`. Running from the current working
    directory matters: `evals-run` always runs `coder-eval` with `cwd=evals/`
    (the Makefile `cd`s there first), and this script is wired the same way
    (see the Makefile's `evals-preflight` target), so the probe's `.env`
    search lands on the same file the real run's would.

    This script parses the probe's result. It does not re-derive anything
    about `API_BACKEND` or `ANTHROPIC_API_KEY` itself.

WHAT IT FLAGS

    A task YAML with at least one `success_criteria` entry whose `type` is
    `llm_judge` and whose `enabled` is not `false`, when the probe above
    reports that `coder_eval` would resolve no judge transport for it.

WHAT IT DOES NOT CATCH

    - `coder-eval` missing from `PATH` entirely. `evals-plan`, which
      `evals-run` also depends on and which runs before this guard, already
      fails the same way in that case — see the Makefile's `evals-run`
      target. This script's own handling of a missing `coder-eval` is
      belt-and-braces, not the path anyone is expected to hit first.
    - Any transport failure that is not "unconfigured" — an expired key, a
      network error, a Bedrock credential that is present but wrong. Those
      fail at call time, mid-run, the way any other API error does; this
      guard only catches the case upstream degrades into a silent 0.0.
    - Malformed task YAML that parses but has the wrong shape for
      `coder_eval`'s own schema. `evals-plan` is what validates that.

When the probe itself cannot be run or its result cannot be parsed — no
`coder-eval` on `PATH`, an unreadable shebang, a probe that exits non-zero or
prints something this script does not recognise — this script says so
plainly and exits non-zero. It never guesses a judge transport into
existence: unable to ask is treated the same as asked and told no.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError as exc:  # pragma: no cover - `make check` installs it first
    print(
        "error: PyYAML is required to read task YAML -- it is declared in"
        " requirements-dev.txt; run 'make check', which installs it into"
        f" .dev-deps/ and puts it on PYTHONPATH ({exc})",
        file=sys.stderr,
    )
    sys.exit(1)

# What the reader should actually DO. Upstream's own dispatch-time message
# (criteria/llm_judge.py) names `--backend bedrock`, which only becomes
# `API_BACKEND` inside coder_eval's own `cli/run_command.py` -- after this
# guard has already run -- and `make evals-run` has no flag passthrough at
# all. `API_BACKEND=bedrock make evals-run` is the form that actually clears
# this guard, so that is the form named here.
_REMEDY = (
    "llm_judge needs a working judge transport for this run:\n"
    "  - ANTHROPIC_API_KEY set, in the shell environment or in evals/.env, or\n"
    "  - API_BACKEND=bedrock make evals-run (Bedrock always has a transport).\n"
    "Set one of the above, or remove/disable the llm_judge criterion.\n"
    "(coder_eval's own dispatch-time message, for reference, names `--backend\n"
    "bedrock` -- that flag is only mirrored into API_BACKEND inside coder_eval's\n"
    "own CLI, and `make evals-run` has no flag passthrough, so it has no effect\n"
    "here. API_BACKEND=bedrock is the form above that actually works.)"
)

# Run under the interpreter `_find_coder_eval_interpreter` locates. Imports
# `coder_eval` fresh and asks it, rather than assuming anything about how it
# resolves its own settings. Kept to two possible outcome lines plus an
# error line, so the parent process has an unambiguous result to parse.
_PROBE_SOURCE = """
import sys
try:
    from coder_eval.config import Settings
    from coder_eval.models import DirectRoute, resolve_route
except Exception as exc:
    print(f"IMPORT_ERROR: {exc}")
    raise SystemExit(1)
try:
    route = resolve_route(Settings())
except Exception as exc:
    print(f"RESOLVE_ERROR: {exc}")
    raise SystemExit(1)
if route is None or (isinstance(route, DirectRoute) and route.judge_transport is None):
    print("NO_TRANSPORT")
else:
    print("TRANSPORT_OK")
"""


class ProbeUnavailable(Exception):
    """The probe could not be run, or its result could not be parsed.

    Raised instead of guessing. Every raise site names what went wrong, so
    `main` can report it plainly rather than falling back to a guess.
    """


def has_enabled_llm_judge(task: object) -> bool:
    """True if `task` (a parsed task YAML) carries a live `llm_judge` row.

    "Live" means `type: llm_judge` and not explicitly `enabled: false` —
    the same gate `LLMJudgeChecker._check_impl_async` applies before it
    would otherwise call a model.
    """
    if not isinstance(task, dict):
        return False
    criteria = task.get("success_criteria")
    if not isinstance(criteria, list):
        return False
    for criterion in criteria:
        if not isinstance(criterion, dict):
            continue
        if criterion.get("type") == "llm_judge" and criterion.get("enabled", True) is not False:
            return True
    return False


def find_coder_eval_interpreter() -> Path:
    """Return the Python interpreter `coder-eval` itself runs under.

    `coder-eval` is a `uv tool install` console script: its shebang line
    names the interpreter of its own dedicated venv — the one `coder_eval`,
    and the settings resolution this script needs to ask about, actually
    live in. Probing under that interpreter, rather than the one running
    this script, means the probe sees exactly what `coder-eval run` would.

    Raises `ProbeUnavailable` when `coder-eval` is not on `PATH`, or its
    shebang cannot be read.
    """
    which = shutil.which("coder-eval")
    if which is None:
        raise ProbeUnavailable(
            "no `coder-eval` on PATH; run `make evals-install` first "
            "(evals-plan, run before this guard, already fails the same "
            "way, so this case is belt-and-braces, not the common one)"
        )
    try:
        with open(which, encoding="utf-8", errors="strict") as handle:
            first_line = handle.readline()
    except (OSError, UnicodeDecodeError) as exc:
        raise ProbeUnavailable(f"could not read {which}'s shebang line: {exc}") from exc
    rest = first_line[2:].strip() if first_line.startswith("#!") else ""
    if not rest:
        raise ProbeUnavailable(f"{which} has no readable shebang line; cannot find its interpreter")
    return Path(rest.split()[0])


def probe_judge_transport(interpreter: Path) -> bool:
    """Ask `coder_eval`, under `interpreter`, whether `llm_judge` has a
    transport in the current working directory.

    Runs `_PROBE_SOURCE`, inheriting this process's cwd so a cwd-relative
    `.env` resolves exactly the way it would for `coder-eval run` — see the
    module docstring's HOW IT DECIDES section.

    Returns True iff the probe reports `coder_eval` would resolve a usable
    judge transport. Raises `ProbeUnavailable` if the probe could not be run
    or its output was not one of the two results it is written to print.
    """
    try:
        result = subprocess.run(
            [str(interpreter), "-c", _PROBE_SOURCE],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except OSError as exc:
        raise ProbeUnavailable(f"could not run {interpreter}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeUnavailable(f"{interpreter} did not finish resolving settings within 30s") from exc

    output = result.stdout.strip()
    if result.returncode != 0 or output not in ("TRANSPORT_OK", "NO_TRANSPORT"):
        detail = output or result.stderr.strip() or f"exit {result.returncode}, no output"
        raise ProbeUnavailable(f"probe under {interpreter} did not run cleanly: {detail}")
    return output == "TRANSPORT_OK"


def main(argv: list[str]) -> int:
    if not argv:
        print("evals-preflight: no task files given; nothing to check")
        return 0

    offending: list[tuple[str, str]] = []
    read_errors: list[str] = []
    for arg in argv:
        path = Path(arg)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            read_errors.append(f"{arg}: {exc}")
            continue
        try:
            task = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            read_errors.append(f"{arg}: invalid YAML ({exc})")
            continue
        if has_enabled_llm_judge(task):
            task_id = task.get("task_id") if isinstance(task, dict) else None
            offending.append((arg, task_id or arg))

    if read_errors:
        for error in read_errors:
            print(f"error: {error}", file=sys.stderr)
        print(
            "\nevals-preflight could not read every task file given; fix the "
            "above before running.",
            file=sys.stderr,
        )
        return 1

    if not offending:
        print(f"evals-preflight: no enabled llm_judge criteria in {len(argv)} task file(s)")
        return 0

    try:
        interpreter = find_coder_eval_interpreter()
        available = probe_judge_transport(interpreter)
    except ProbeUnavailable as exc:
        print(
            f"error: could not ask coder_eval whether a judge transport is "
            f"configured: {exc}",
            file=sys.stderr,
        )
        print(
            f"\n{len(offending)} row(s) carry an enabled llm_judge criterion "
            f"and could not be checked:",
            file=sys.stderr,
        )
        for arg, task_id in offending:
            print(f"  - {task_id} ({arg})", file=sys.stderr)
        print(f"\n{_REMEDY}", file=sys.stderr)
        return 1

    if available:
        print(
            f"evals-preflight: judge transport available; {len(offending)} "
            f"llm_judge row(s) among {len(argv)} task file(s) can run"
        )
        return 0

    print(
        f"error: {len(offending)} row(s) carry an enabled llm_judge criterion, "
        "and no judge transport is configured for this run:",
        file=sys.stderr,
    )
    for arg, task_id in offending:
        print(f"  - {task_id} ({arg})", file=sys.stderr)
    print(f"\n{_REMEDY}", file=sys.stderr)
    print(
        "\nThe run was NOT started. Proceeding would produce a report whose "
        "llm_judge finding criteria never execute — coder_eval scores each as "
        "0.0 and continues, so the report reads like a real result and is not "
        "one.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
