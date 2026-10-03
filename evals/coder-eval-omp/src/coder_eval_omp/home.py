"""Which files of a real Omp home the throwaway home may borrow.

Pure on purpose, like `rpc`: `scripts/check-omp-agent.py` drives it with
nothing installed.

A run needs a model, and Omp keeps the model and its credentials in the real
`~/.omp/agent/`. Everything else in that directory is a person's own setup, and
borrowing it makes the bare arm stop being bare. So the home is inherited by
allow list, never by "everything except".
"""

from __future__ import annotations

from pathlib import Path


#: The files that carry providers and credentials, in Omp 18.4.10:
#:
#: - `models.yml` holds custom providers.
#: - `agent.db` is Omp's "SQLite database for settings and auth storage"
#:   (`pi-utils/src/dirs.ts`, `getAgentDbPath`); the `-wal` and `-shm` siblings
#:   are its write-ahead log and shared memory, which a database in WAL mode
#:   needs beside it to read the same state.
#: - `secrets.yml` holds secrets that `models.yml` can reference.
#:
#: Left out by name, so a later "just add this one" meets the reason:
#:
#: - `mcp.json` is a person's MCP servers. Omp enables every connected MCP tool
#:   whatever `--tools` says, so an inherited one reaches both arms and escapes
#:   the row's tool list (measured, `docs/notes/0013-the-omp-arm.md`).
#: - `AGENTS.md`, `SYSTEM.md`, `SYSTEM_TEMPLATE.md`, `PERSONALITY.md` and
#:   `RULES.md` are a person's own instructions. Inherited, they load into the
#:   bare arm and into the treated arm's baseline alike.
#: - Caches and everything else the directory accumulates.
#:
#: `config.yml` is written by the agent instead of borrowed.
PROVIDER_FILES: tuple[str, ...] = (
    "models.yml",
    "agent.db",
    "agent.db-wal",
    "agent.db-shm",
    "secrets.yml",
)


def inherited_files(real_agent_dir: Path) -> list[Path]:
    """The files of `real_agent_dir` the throwaway home symlinks in.

    Only regular files named in `PROVIDER_FILES` that exist there; directories
    were never linked and stay unlinked.
    """
    return [
        real_agent_dir / name
        for name in PROVIDER_FILES
        if (real_agent_dir / name).is_file()
    ]
