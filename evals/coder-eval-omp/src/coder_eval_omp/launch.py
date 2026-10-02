"""How the `omp` agent kind starts Omp: the config, the argv and the environment.

Pure, for the reason `tools.py` is: `scripts/check-omp-agent.py` runs it in
`make check` with no `coder_eval` and no `omp` installed. What it builds is the
sandbox boundary `docs/notes/0013-the-omp-arm.md` records, so it is built here
where it can be asserted rather than inline in `agent.py`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from importlib.resources import files
from pathlib import Path

from .tools import ToolSelection, UnenforceableToolList


#: Written into the throwaway Omp home as `config.yml`.
#:
#: Skill commands are off by default, and with them off `get_available_commands`
#: reports the builtins alone, so the run could not record which skills it
#: loaded. `fetch.enabled: false` stops `read` and `grep` from opening any
#: http(s) URL, a bare `www.host` included, which no pattern in the guard can
#: catch. No row needs fetch: `WebFetch` has no Omp twin, so `tools.py` refuses
#: a row that allows it.
OMP_CONFIG = "skills:\n  enableSkillCommands: true\nfetch:\n  enabled: false\n"

#: The child environment variable `eval_guard.js` reads the row's grant from.
TOOLS_ENV = "CODER_EVAL_OMP_TOOLS"


def guard_path() -> Path:
    """The eval guard extension, shipped inside this package."""
    return Path(str(files(__package__).joinpath("eval_guard.js")))


def reject_tool_flags(extra_args: Sequence[str]) -> None:
    """Refuse a tool flag in `extra_args`.

    The row's tool lists are the one grant: Omp gets it as `--tools`, and the
    guard gets it as `TOOLS_ENV`. A second `--tools` here would change what Omp
    offers without changing what the guard allows, so the two would disagree.
    An experiment that needs another tool changes the row's `allowed_tools`.
    """
    flags = [arg for arg in extra_args if arg == "--no-tools" or arg.split("=", 1)[0] == "--tools"]
    if flags:
        raise UnenforceableToolList(
            f"omp: extra_args carries {', '.join(map(repr, flags))}; grant tools through the row's "
            "allowed_tools, so Omp and the eval guard read the same grant"
        )


def rpc_argv(binary: str, tools: ToolSelection, extra_args: Sequence[str]) -> list[str]:
    """The `omp --mode rpc` command line.

    The guard loads in both arms, so the ablation stays symmetric. `extra_args`
    may not carry a tool flag; `reject_tool_flags` says why.
    """
    reject_tool_flags(extra_args)
    return [binary, "--mode", "rpc", "-e", str(guard_path()), *tools.argv, *extra_args]


def child_env(
    base: Mapping[str, str],
    home: Path,
    path_prepend: Sequence[str],
    tools: ToolSelection,
) -> dict[str, str]:
    """The child's environment: `base`, pointed at the throwaway home.

    The PATH prepend is `Agent.start`'s mock-shadowing contract: the sandbox's
    mock CLI directories must resolve before the real binaries, or a task
    grading a mocked CLI silently exercises the real one. `TOOLS_ENV` tells the
    guard which tools the row granted.
    """
    env = dict(base)
    if path_prepend:
        env["PATH"] = os.pathsep.join([*path_prepend, env.get("PATH", "")])
    env["HOME"] = str(home)
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        env[name] = str(home / name.lower())
    env[TOOLS_ENV] = ",".join(tools.tools)
    return env
