#!/usr/bin/env python3
"""The repository stanza that enables this plugin, derived rather than typed.

Enablement is per-repository: a repository declares the plugin for everyone
who works in it — a laptop CLI and a cloud session alike — by carrying
`extraKnownMarketplaces` + `enabledPlugins` in its `.claude/settings.json`.
Installation is the other half, and is per-machine or per-environment; see
docs/bootstrapping-a-repository.md. A repository whose stanza is wrong
silently runs without the plugin, so the stanza is the thing that must never
be subtly wrong.

Two of its three values are easy to get wrong by hand, and both are read from
the manifests here rather than written out:

- The **marketplace name** is `marketplace.json`'s `name`, which is the
  repository's name. Measured: `claude plugin marketplace add
  jmcvetta/daily-driver` registers it under exactly that name.
- The **enablement key** is `plugin@marketplace`, so it is
  `daily-driver@daily-driver`. The repetition is real rather than a typo:
  the repository and the plugin it ships carry the same name. An
  `enabledPlugins` entry naming an unregistered marketplace is skipped as
  orphaned, and nothing reports it.

Modes:

    python3 scripts/stanza.py                 print the stanza
    python3 scripts/stanza.py --write REPO    merge it into REPO's settings

`--write` is the laptop-side helper for a repository that predates the
template. It deliberately lives in this repository's checkout and not in the
plugin: a skill shipped inside the plugin could never bootstrap the one
repository that needs it, since a missing stanza is why the plugin — and so
the skill — did not load. Bootstrapping is an act performed from outside.

No third-party imports: this runs from a Makefile on a laptop and from CI, and
a dependency install between the two is a place for them to differ.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

MARKETPLACES_KEY = "extraKnownMarketplaces"
PLUGINS_KEY = "enabledPlugins"


def owner_repo(url: str) -> str:
    """`owner/repo` from a `repository` URL, in either form git writes it.

    The marketplace source wants `owner/repo`, and a source that is anything
    else resolves to no marketplace — the silent failure this whole file
    exists to prevent — so an SSH-form remote must not be allowed to reach it.
    `git@github.com:owner/repo.git` carries the path after a colon and has no
    `//`, which is how it is told apart from `https://host/owner/repo`, whose
    only colon belongs to the scheme.
    """
    cleaned = url.strip().rstrip("/").removesuffix(".git")
    if "//" not in cleaned:
        cleaned = cleaned.rpartition(":")[2]
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) < 2:
        raise SystemExit(
            f"error: cannot read owner/repo from plugin.json repository {url!r}"
        )
    return "/".join(parts[-2:])


def canonical() -> dict:
    """The stanza, built from the two manifests it has to agree with."""
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    marketplace = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())

    return {
        MARKETPLACES_KEY: {
            marketplace["name"]: {
                "source": {
                    "source": "github",
                    "repo": owner_repo(plugin["repository"]),
                },
            },
        },
        PLUGINS_KEY: {
            f"{plugin['name']}@{marketplace['name']}": True,
        },
    }


def render(stanza: dict) -> str:
    return json.dumps(stanza, indent=2) + "\n"


def merge(settings: dict, stanza: dict) -> list[str]:
    """Fold the stanza into `settings` in place. Returns what changed."""
    changes: list[str] = []
    for section, entries in stanza.items():
        current = settings.setdefault(section, {})
        if not isinstance(current, dict):
            raise SystemExit(f"error: existing {section} is not an object")
        for key, value in entries.items():
            if current.get(key) == value:
                continue
            # An entry under the same name with a different value is the
            # interesting case — a stale source, or a hand-edit — so say so
            # rather than silently replacing it.
            if key in current:
                changes.append(f"replaced {section}.{key}")
            else:
                changes.append(f"added {section}.{key}")
            current[key] = value
    return changes


def write(target: Path) -> int:
    if not target.is_dir():
        print(f"error: {target} is not a directory", file=sys.stderr)
        return 1

    path = target / ".claude" / "settings.json"
    if path.exists():
        try:
            settings = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            print(f"error: {path} is not valid JSON: {exc}", file=sys.stderr)
            return 1
        if not isinstance(settings, dict):
            print(f"error: {path} is not a JSON object", file=sys.stderr)
            return 1
    else:
        settings = {}

    changes = merge(settings, canonical())
    if not changes:
        print(f"{path}: stanza already present")
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n")
    for change in changes:
        print(f"{path}: {change}")
    print("Commit it, and trust the folder — an untrusted folder ignores it.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--write",
        metavar="REPO",
        type=Path,
        help="merge the stanza into REPO/.claude/settings.json",
    )
    args = parser.parse_args()

    if args.write is not None:
        return write(args.write)
    print(render(canonical()), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
