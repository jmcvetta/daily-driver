#!/usr/bin/env python3
"""Refuse to start an eval run whose arms cannot be resolved.

`coder-eval plan` validates the task files and says nothing useful about the
variants. Measured, with an experiment declaring `agent: {type: omp}` and no
plugin installed:

    Variant 'omp': resolution failed - No agent registered for type 'omp'.
    Registered kinds: ['antigravity', 'claude-code', 'codex', 'none', 'opencode']
    All tasks are valid!

and it exited 0. So `make evals-plan` cannot be the thing that catches a
misconfigured arm — the failure is printed, the command succeeds, and the next
paid run measures an arm that never started. This script is the guard issue
#173 asks for. It is free: it calls no model and reads no task file.

HOW IT DECIDES

    It asks `coder_eval`, the way `evals-preflight.py` does and for the same
    reason: a copy of the resolution rule in this repository is a copy that can
    drift from it. `coder-eval` on `PATH` is a `uv tool install` console script
    whose shebang names its own venv's interpreter, which is where `coder_eval`
    and any installed agent plugin actually live. The probe runs under THAT
    interpreter, loads the plugin entry points, reads the experiment file, and
    reports the registered kinds and every variant's resolved agent kind.

WHAT IT FLAGS

    An experiment variant whose agent kind no agent is registered for — the
    measured failure above, which is what an un-installed `coder-eval-omp` or
    `coder-eval-codex` looks like.
    An experiment file that does not parse, or that declares no variants.

WHAT IT DOES NOT FLAG

    Whether the arm then works. A registered kind can still fail to start
    `omp` or the Codex app-server, fail to install the plugin, or load nothing;
    those failures are loud at run time by design, and `environment_info`
    records what loaded.
    That the RIGHT Codex kind is named. `codex` is a registered built-in and
    resolves cleanly, and it is the wrong kind for these suites: it hands the
    judge bare text, so every judged row scores 0.0. `evals/experiments/codex.yaml`
    says so where it names `codex-daily-driver`; nothing here can.
    Whether the model named by a variant exists.

No third-party imports beyond PyYAML, declared in the root `pyproject.toml`'s
dev group.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


try:
    import yaml
except ImportError as exc:  # pragma: no cover - `make check` installs it first
    print(
        "error: PyYAML is required to read experiment YAML -- it is declared"
        " in the root pyproject.toml's dev group; run 'make check', which"
        f" runs the legs under uv (installed into .venv from uv.lock) ({exc})",
        file=sys.stderr,
    )
    sys.exit(1)


_REMEDY = (
    "An arm whose agent kind is not registered runs nothing and reports zeros.\n"
    "  - `omp` comes from evals/coder-eval-omp/, installed by `make evals-install`.\n"
    "  - `codex-daily-driver` comes from evals/coder-eval-codex/, installed by the same target.\n"
    "  - Re-run `make evals-install` if the tool environment was rebuilt.\n"
    "Then run `make evals-plan` again."
)

# Run under the interpreter `find_coder_eval_interpreter` locates. Prints one
# JSON object, so the parent has an unambiguous result to parse rather than a
# log to scrape.
_PROBE_SOURCE = """
import json, sys
try:
    from coder_eval.agents.registry import AgentRegistry
    from coder_eval.plugins import load_plugins
except Exception as exc:
    print(json.dumps({"error": f"import failed: {exc}"}))
    raise SystemExit(1)
try:
    load_plugins()
except Exception as exc:
    print(json.dumps({"error": f"plugin load failed: {exc}"}))
    raise SystemExit(1)
print(json.dumps({"kinds": AgentRegistry.list_kinds()}))
"""


class ProbeUnavailable(Exception):
    """The probe could not be run, or its result could not be parsed."""


def find_coder_eval_interpreter() -> Path:
    """The Python interpreter `coder-eval` itself runs under.

    Same resolution as `evals-preflight.py`: the console script's shebang names
    its own venv, which is the environment a plugin is installed into.
    """
    which = shutil.which("coder-eval")
    if which is None:
        raise ProbeUnavailable("no `coder-eval` on PATH; run `make evals-install` first")
    try:
        with open(which, encoding="utf-8", errors="strict") as handle:
            first_line = handle.readline()
    except (OSError, UnicodeDecodeError) as exc:
        raise ProbeUnavailable(f"could not read {which}'s shebang line: {exc}") from exc
    rest = first_line[2:].strip() if first_line.startswith("#!") else ""
    if not rest:
        raise ProbeUnavailable(f"{which} has no readable shebang line; cannot find its interpreter")
    return Path(rest.split()[0])


def registered_kinds(interpreter: Path) -> list[str]:
    """The agent kinds `coder_eval` has registered, plugins included."""
    try:
        result = subprocess.run(
            [str(interpreter), "-c", _PROBE_SOURCE],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as exc:
        raise ProbeUnavailable(f"could not run {interpreter}: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeUnavailable(f"{interpreter} did not finish loading plugins within 60s") from exc

    output = result.stdout.strip().splitlines()
    payload: dict[str, object] = {}
    for line in reversed(output):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict):
            payload = candidate
            break
    if "error" in payload:
        raise ProbeUnavailable(str(payload["error"]))
    kinds = payload.get("kinds")
    if not isinstance(kinds, list):
        detail = result.stderr.strip() or f"exit {result.returncode}, no parseable output"
        raise ProbeUnavailable(f"probe under {interpreter} did not run cleanly: {detail}")
    return [str(kind) for kind in kinds]


def variant_kinds(path: Path) -> list[tuple[str, str | None]]:
    """Each variant of an experiment file, with the agent kind it resolves to.

    A variant inherits `defaults.agent.type` where it declares none of its own,
    which is the layering `coder_eval` applies; a kind of None means neither
    layer named one, and the run would take it from the CLI instead.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError(f"{path} does not parse as a mapping")
    defaults = document.get("defaults") or {}
    default_agent = defaults.get("agent") if isinstance(defaults, dict) else None
    default_kind = default_agent.get("type") if isinstance(default_agent, dict) else None

    variants = document.get("variants")
    if not isinstance(variants, list) or not variants:
        raise ValueError(f"{path} declares no variants")

    resolved: list[tuple[str, str | None]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            raise ValueError(f"{path} has a variant that is not a mapping")
        agent = variant.get("agent")
        kind = agent.get("type") if isinstance(agent, dict) else None
        resolved.append((str(variant.get("variant_id") or "<unnamed>"), kind or default_kind))
    return resolved


def main(argv: list[str]) -> int:
    if not argv:
        print("evals-variants: no experiment files given; nothing to check")
        return 0

    try:
        kinds = registered_kinds(find_coder_eval_interpreter())
    except ProbeUnavailable as exc:
        print(f"evals-variants: {exc}", file=sys.stderr)
        return 1

    failures: list[str] = []
    checked = 0
    for arg in argv:
        path = Path(arg)
        try:
            variants = variant_kinds(path)
        except (OSError, ValueError, yaml.YAMLError) as exc:
            failures.append(f"{path}: {exc}")
            continue
        for variant_id, kind in variants:
            checked += 1
            if kind is None:
                failures.append(f"{path}: variant {variant_id!r} names no agent type")
            elif kind not in kinds:
                failures.append(
                    f"{path}: variant {variant_id!r} wants agent kind {kind!r}, which is not registered"
                )

    if failures:
        print("evals-variants: an arm would not resolve:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        print(f"  registered kinds: {kinds}", file=sys.stderr)
        print(_REMEDY, file=sys.stderr)
        return 1

    print(f"evals-variants: {checked} variant(s) across {len(argv)} experiment(s) resolve to registered agents")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
