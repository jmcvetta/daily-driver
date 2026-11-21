"""Place a ``plugins:`` root's skills where the Codex CLI discovers them.

The CLI scans ``.agents/skills`` from the working directory up to the repository
root, and follows symlinked skill folders. That is the same directory shape
coder_eval's SDK agent used, so one layout serves both; the difference is that
this module links the directories itself, because the CLI has no SDK setup hook
to do it.

Why the root is resolved first: the experiments write ``path: ".."`` relative to
the ``evals/`` directory every run target changes into. ``CodexAgent._setup_skills``
symlinked each skill by the path it was handed, so a relative root produced
links whose bodies pointed back at their own directory — one entry per skill and
not one readable ``SKILL.md`` — and the treated arm then measured a model with no
skills at all. ``plugins.resolve_local_plugins`` is applied before this module,
so every root here is absolute and checked.

A declared plugin that yields no readable skill is fatal, not a warning: an arm
that runs untreated reports zeros that read exactly like a skill that never
fired. The message is raised as the caller's typed config error so the harness
does not retry a deterministic configuration fault as a network problem.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .plugins import resolve_local_plugins


logger = logging.getLogger(__name__)

#: Where both Codex and the former SDK agent look for project skills.
SKILLS_DIR = Path(".agents") / "skills"


class SkillLinkError(RuntimeError):
    """A declared plugin root produced no skill the CLI could read."""


def _skill_dirs(root: Path) -> list[Path]:
    """The skill folders under one plugin root.

    A plugin root holds ``skills/<name>/SKILL.md``. A directory without a
    readable ``SKILL.md`` is not a skill and is skipped; the caller reports zero
    as fatal.
    """
    skills = root / "skills"
    if not skills.is_dir():
        return []
    found: list[Path] = []
    for entry in sorted(skills.iterdir()):
        if entry.is_dir() and (entry / "SKILL.md").is_file():
            found.append(entry)
    return found


def link_skills(plugins: list[object], *, base: Path, workspace: Path) -> list[str]:
    """Link every declared plugin's skills into ``workspace/.agents/skills``.

    Returns the skill names linked, sorted, after verifying each one resolves to
    a readable ``SKILL.md``. ``base`` is what a relative plugin path is resolved
    against — the process working directory, matching the other arms.

    Raises ``SkillLinkError`` when plugins were declared and no readable skill
    arrived, so the run cannot silently measure an untreated session.
    """
    if not plugins:
        return []
    roots = resolve_local_plugins(list(plugins), base=base)
    destination = workspace / SKILLS_DIR
    destination.mkdir(parents=True, exist_ok=True)

    linked: list[str] = []
    for root in roots:
        root_path = Path(str(root["path"]))
        for skill in _skill_dirs(root_path):
            target = destination / skill.name
            if target.is_symlink() or target.exists():
                if target.is_dir() and not target.is_symlink():
                    # A real directory in the sandbox is not a stale link from a
                    # previous run; leave it rather than deleting task content.
                    raise SkillLinkError(f"{target} already exists and is not a symlink; refusing to replace it")
                target.unlink()
            try:
                os.symlink(skill, target, target_is_directory=True)
            except OSError as exc:
                raise SkillLinkError(f"could not link skill {skill} to {target}: {exc}") from exc
            if (target / "SKILL.md").is_file():
                linked.append(skill.name)
            else:
                raise SkillLinkError(f"linked {target} but its SKILL.md is not readable")

    if not linked:
        raise SkillLinkError(
            "plugins were declared but no readable skill was found under "
            + ", ".join(str(Path(str(root["path"]))) for root in roots)
            + "; the treated arm would run without the skills under test"
        )
    logger.info("codex: linked %d skill(s) into %s: %s", len(linked), destination, sorted(linked))
    return sorted(linked)
