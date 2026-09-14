"""Plugin roots, resolved — with no `coder_eval` in sight.

Pure, for the reason `transcript.py` is: the agent cannot be exercised without a
`coder_eval` install and the Codex SDK, so what is load-bearing lives here and
`scripts/check-codex-agent.py` drives it in `make check`.

**What it is for.** `CodexAgent._setup_skills` links a plugin root's skills into
`<task cwd>/.agents/skills/<name>` with `target.symlink_to(skill_dir)`, and
`skill_dir` is built from `config.plugins[].path` exactly as written. The
experiments here write `path: ".."`, relative to the `evals/` directory both run
targets `cd` into — which is correct for the Claude agent, because
`coder_eval` resolves plugin paths before that agent sees them, and wrong for
the Codex one, which does not go through that resolution.

Measured, with the repository's real layout: a relative root makes every link
body relative too, so `.agents/skills/pr -> ../skills/pr` resolves back to the
link's own directory and points at itself. One entry per skill is created and
not one has a readable `SKILL.md`. The treated arm then runs with no skills at
all, every trigger row scores 0, and the run costs full price — which is the
silent zero this whole arm exists to prevent, arriving through the arm itself.

`_setup_skills`'s own "0 skills linked" warning does not fire on it: broken
links still count as directory entries.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping


class PluginPathError(RuntimeError):
    """A `plugins:` entry that cannot be turned into a usable root.

    A plain `RuntimeError` subclass, because this module imports nothing — that
    is what lets `scripts/check-codex-agent.py` drive it with no `coder_eval`
    installed. It is NOT the exception the agent raises: `coder_eval`
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
