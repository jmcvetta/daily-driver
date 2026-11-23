"""Plugin roots, resolved — with no `coder_eval` in sight.

Pure, for the reason `transcript.py` is: the agent cannot be exercised without
an installed, subscription-authenticated `codex` executable. The plugin-root
resolution lives here and is consumed by `skills.py` before the CLI starts.

**Why a root must be absolute.** The CLI scans `<cwd>/.agents/skills` and every
parent up to the repository root, following symlinks. A relative root makes
every link body relative too, so `.agents/skills/pr -> ../skills/pr` resolves
back to the link's own directory and points at itself. One entry per skill is
created and not one has a readable `SKILL.md`; the treated arm then runs with no
skills and every trigger row scores 0, at the run's full allowance cost. The
experiments write `path: ".."`, relative to the `evals/` directory every run
target changes into, so resolution against that base is what keeps the arm
treated.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


class PluginPathError(RuntimeError):
    """A `plugins:` entry that cannot be turned into a usable root.

    A plain `RuntimeError` subclass, because this module imports nothing. It is
    NOT the exception the agent raises: `coder_eval`
    categorises a bare `RuntimeError` as the retryable `AGENT_API_ERROR`, so a
    deterministic path failure would be retried three times with backoff, the
    Codex client re-spawned each time, and finally reported as a network
    problem. `agent.py` catches this and re-raises `coder_eval`'s typed
    `AgentConfigError`, which is non-retryable by `isinstance`.
    """


def resolve_local_plugins(plugins: list[Any], *, base: Path) -> list[dict[str, Any]]:
    """Every `type: local` plugin entry, with its `path` made absolute.

    `base` is what a relative path is resolved against — the process working
    directory in the agent, and a temporary directory in the test. Environment
    variables are expanded first, the way `CodexAgent._setup_skills` expands
    them, so a root written as `$SKILLS_REPO_PATH` resolves identically.

    Raises `PluginPathError` rather than warning. A declared plugin that does
    not resolve is an arm that runs without the skills under test and reports
    zeros, which reads exactly like a skill that never fires — the same reason
    `coder_eval_omp`'s `_link_plugins` treats it as fatal.
    """
    resolved: list[dict[str, Any]] = []
    for plugin in plugins:
        if not isinstance(plugin, Mapping):
            raise PluginPathError(f"a `plugins:` entry is not a mapping: {plugin!r}")
        entry = dict(plugin)
        if entry.get("type") != "local":
            raise PluginPathError(f"only `type: local` plugin entries are supported; got {plugin!r}")
        path = entry.get("path")
        if not path:
            raise PluginPathError(f"a `type: local` plugin entry declares no path: {plugin!r}")
        expanded = os.path.expandvars(str(path))
        root = Path(expanded)
        if not root.is_absolute():
            root = base / root
        root = root.resolve()
        if not root.is_dir():
            hint = "env var likely unset" if "$" in expanded else "path does not exist"
            raise PluginPathError(f"plugin path {path!r} resolved to {root}, which is not a directory ({hint})")
        entry["path"] = str(root)
        resolved.append(entry)
    return resolved
