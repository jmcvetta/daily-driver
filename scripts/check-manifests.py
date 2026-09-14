#!/usr/bin/env python3
"""The manifest checks `claude plugin validate` does not make.

`claude plugin validate --strict` covers most of what can go wrong in a
plugin, and everything it covers is left to it. Four things it lets through
are checked here, each measured against the CLI rather than assumed:

- A skill whose frontmatter `name` disagrees with its directory. `validate`
  passes it; Claude Code resolves the skill by directory, so the name in the
  file is the one that is wrong and nothing says so.
- An agent whose frontmatter `name` disagrees with its filename. Agents resolve
  the other way round -- by the frontmatter `name`, measured -- so the file is
  the misleading half, and a reader looking for `logic-reviewer` finds nothing.
- Two agents claiming one `name`. Only one of them is dispatchable; the other
  is silently shadowed, and `validate --strict` says nothing.
- A `description:` present but empty, in a skill or an agent. `validate` warns
  only when the key is missing outright, so `description: ""` is green under
  `--strict` and the component reaches users with nothing to trigger on.
- A skill `description:` longer than Codex renders. Codex's prompt renderer
  cuts a description mid-word and appends `...` -- measured against
  `codex-cli` 0.154.0. Nothing warns: the skill still loads, and the tail that
  was doing the discriminating simply is not there. `validate` never sees
  Codex at all, so this is the only leg that can catch it.
- A `name` or a `description` disagreeing between plugin.json and its
  marketplace entry, or a `name` disagreeing between the marketplace and the
  repository it names. `validate` reads one manifest at a time, so it never
  compares them. (It *does* compare the `version` fields, so those are its job
  and not this script's.) The description is written twice on purpose -- the
  marketplace listing renders one copy and `claude plugin details` the other --
  so a drift shows up to users and to nothing else.
- Root `package.json` (the Omp runtime adapter's manifest, name
  `daily-driver`) disagreeing with plugin.json or the marketplace entry about
  the plugin name or version, or missing or mispointing the Omp extension
  entry. Release-please bumps the three manifests together, so a tree where
  they disagree has already drifted.
- A `SKILL.md` naming a harness's own tool routes in its body. The skills run
  on Claude Code, on Omp and on Codex, and the routes differ; `0011` puts the
  body's operation in words and the call in
  `skills/<name>/references/claude.md`, `references/omp.md` or
  `references/codex.md`. A route written back into the body is not wrong on the
  harness it was written for, which is exactly why nothing else catches it: it
  reads correctly, and it is silently wrong on the other two.
- A reference file no `SKILL.md` links, or a reference link that resolves to
  nothing. The move only works if the session opens the file when the skill
  fires, and the link is the whole of that pointer. An unlinked file is a
  route nobody is sent to; a broken link sends them nowhere. Neither fails
  anything else — the skill still loads, and still looks complete.
- A copy of the repository stanza — the template, this repository's own
  `.claude/settings.json`, a fenced block in the documentation — that has
  drifted from the marketplace and plugin names it enables. `validate` does not
  read settings files at all, and a stanza naming a marketplace that does not
  exist enables nothing while looking entirely correct. See `stanza.py`. A
  documented block may quote part of the stanza; a block deliberately showing
  a wrong one — prose walking through a failure mode — is exempted with
  `<!-- stanza-check: ignore -->` above it.

No third-party imports: this runs from a Makefile on a laptop and from CI,
and a dependency install between the two is a place for them to differ.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import stanza

ROOT = Path(__file__).resolve().parent.parent

# Fenced JSON in the prose. Documentation is where the cold start is served
# from -- a person with no plugin and no tooling copies a block out of a file
# -- so a block that has drifted is a silent failure handed out on purpose.
JSON_BLOCK = re.compile(r"^```json\n(.*?)^```", re.DOTALL | re.MULTILINE)

# The one block that must not be checked is the one printing a stanza known to
# be wrong, which prose explaining a failure mode has to be free to show, so a
# block preceded by this marker is skipped. It has to be the last thing before
# the fence, so it cannot be left behind by an edit that moves the block it was
# written for.
IGNORE = re.compile(r"<!--\s*stanza-check:\s*ignore\s*-->\s*\Z")

# The harness routes a `SKILL.md` body may not name. One pattern per rule,
# named, so a failure says which rule it broke rather than which alternation
# branch matched. `${CLAUDE_PLUGIN_ROOT}` is matched braced or not: the
# unbraced spelling is an equally valid shell expansion and is the likelier
# way the rule gets broken.
ROUTES = {
    "mcp__": re.compile(r"mcp__"),
    "AskUserQuestion": re.compile(r"AskUserQuestion"),
    "request_user_input": re.compile(r"request_user_input"),
    "/code-review": re.compile(r"/code-review"),
    "$CLAUDE_PLUGIN_ROOT": re.compile(r"\$\{?CLAUDE_PLUGIN_ROOT\}?"),
    "daily_driver_": re.compile(r"daily_driver_"),
    "run_watch": re.compile(r"run_watch"),
    "skill://": re.compile(r"skill://"),
    "codex CLI": re.compile(
        r"\bcodex (?:exec|review|queue|agents|resume|fork|archive|unarchive"
        r"|delete|plugin|app-server)\b"
    ),
    "agent_tasks tool": re.compile(
        r"\b(?:agent_tasks|create_thread|fork_thread|read_thread|wait_threads"
        r"|list_threads|list_archived_threads|send_message_to_thread"
        r"|set_thread_title|set_thread_archived)\b"
    ),
}

# What Codex's prompt renderer keeps of a `description`. Beyond this the
# description is cut mid-word and `...` is appended, so the tail triggers
# nothing on that harness -- and the cut lands in the middle of the sentences
# that discriminate, because those come last. Claude Code and Omp render the
# whole thing, so a description over the cap reads as correct on two harnesses
# out of three.
#
# 1021 rather than 1024, which is what the four cut descriptions rendered as:
# 1021 characters plus a three-character ellipsis. 1021 is therefore the
# amount of text the renderer is measured to keep, while the length at which
# it starts cutting is only bracketed -- 1013 rendered whole, 1034 cut -- so
# the number the measurement actually supports is the smaller one.
#
# Characters, not bytes: the four cut descriptions carried different numbers
# of em-dashes and all landed on the same rendered length, which a byte cut
# could not produce.
DESCRIPTION_CAP = 1021

# A markdown link into the skill's own `references/` directory. The link text
# is not read: what matters is the target, which is what a reader follows and
# what has to resolve.
REFERENCE_LINK = re.compile(r"\]\(\s*(references/[^)\s]+)\s*\)")

# Not a YAML parser, and not trying to be. Skill frontmatter here is flat
# `key: value` with folded scalars, so this reads exactly that shape and
# reports anything else as unparseable rather than guessing at it.
KEY = re.compile(r"([A-Za-z0-9_-]+):(.*)$")
BLOCK_SCALAR = {">", ">-", ">+", "|", "|-", "|+"}


def frontmatter(path: Path) -> dict[str, str] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = next(
        (i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None
    )
    if end is None:
        return None

    fields: dict[str, list[str]] = {}
    key: str | None = None
    for line in lines[1:end]:
        match = KEY.match(line)
        if match and not line[:1].isspace():
            key = match.group(1)
            fields[key] = [match.group(2).strip()]
        elif key is not None:
            fields[key].append(line.strip())
    return {name: unfold(parts) for name, parts in fields.items()}


def unfold(parts: list[str]) -> str:
    head, *rest = parts
    if head in BLOCK_SCALAR:
        head = ""
    return " ".join(part for part in [head, *rest] if part).strip().strip("\"'")


def load_json(path: Path, errors: list[str]) -> object | None:
    """Parse `path`, reporting a bad file the way every other check reports.

    A settings file people hand-edit is exactly where a trailing comma turns
    up, and a traceback there both reads as a broken check and abandons the
    copies not yet looked at.
    """
    where = path.relative_to(ROOT)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{where}: not valid JSON: {exc}")
        return None
    except OSError as exc:
        errors.append(f"{where}: cannot be read: {exc}")
        return None


def section_of(parsed: object, section: str) -> dict | None:
    """A stanza section of `parsed`, or None if it has none worth comparing."""
    if not isinstance(parsed, dict):
        return None
    entries = parsed.get(section)
    return entries if isinstance(entries, dict) else None


def stanza_errors() -> list[str]:
    """Every copy of the stanza, measured against the manifests."""
    errors: list[str] = []
    expected = stanza.canonical()

    # The template is copied wholesale into a new repository, so it is the one
    # copy that must be the stanza and nothing else.
    template = ROOT / "template" / ".claude" / "settings.json"
    if not template.exists():
        errors.append(f"{template.relative_to(ROOT)}: missing")
    else:
        parsed = load_json(template, errors)
        if parsed is not None and parsed != expected:
            errors.append(
                f"{template.relative_to(ROOT)}: does not match the stanza "
                "`python3 scripts/stanza.py` prints"
            )

    # This repository carries the stanza too, and may grow other settings
    # around it, so it is checked for containment rather than equality.
    own = ROOT / ".claude" / "settings.json"
    if not own.exists():
        errors.append(f"{own.relative_to(ROOT)}: missing")
    else:
        settings = load_json(own, errors)
        if settings is not None:
            for section, entries in expected.items():
                present = section_of(settings, section)
                for key, value in entries.items():
                    if present is None or present.get(key) != value:
                        errors.append(
                            f"{own.relative_to(ROOT)}: {section}.{key} is "
                            "missing or disagrees with the stanza"
                        )

    docs = [ROOT / "README.md", *sorted(ROOT.glob("docs/**/*.md"))]
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        where = doc.relative_to(ROOT)
        for match in JSON_BLOCK.finditer(text):
            block = match.group(1)
            if not any(key in block for key in expected):
                continue
            if IGNORE.search(text[: match.start()]):
                continue
            try:
                parsed = json.loads(block)
            except json.JSONDecodeError as exc:
                errors.append(f"{where}: stanza block is not valid JSON: {exc}")
                continue
            if not isinstance(parsed, dict):
                errors.append(f"{where}: stanza block is not a JSON object")
                continue
            # A block is allowed to quote part of the stanza — one section, or
            # one entry of one — since the prose walks through the halves
            # separately. What it may not do is name a key the stanza does not
            # have, or give one a different value: that is the drift being
            # hunted, and it looks entirely correct on the page.
            for section, entries in expected.items():
                present = parsed.get(section)
                if present is None:
                    continue
                if not isinstance(present, dict):
                    errors.append(f"{where}: stanza block's {section} is not an object")
                    continue
                for key, value in present.items():
                    if key not in entries:
                        errors.append(
                            f"{where}: stanza block's {section} names {key!r}, "
                            "which is not in the stanza `python3 "
                            "scripts/stanza.py` prints"
                        )
                    elif value != entries[key]:
                        errors.append(
                            f"{where}: stanza block's {section}.{key} disagrees "
                            "with `python3 scripts/stanza.py`"
                        )
    return errors


def body_of(path: Path) -> tuple[str, int]:
    """A component's body and the line its body starts on.

    The frontmatter is exempt from the route rules, and that exemption is the
    point rather than a concession: the `description` is what triggers the
    skill, so a skill that fires on a tool call has to name that call — on
    every harness — to fire on any of them. A file with no frontmatter is all
    body, which is the safe reading: it exempts nothing.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return text, 1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "\n".join(lines[i + 1 :]), i + 2
    return text, 1


def reference_errors(skills: list[Path]) -> list[str]:
    """The three things `0011`'s reference-file split needs to stay true.

    No route in a body, no reference file nothing links to, and no link that
    resolves to nothing. See the docstring for why each one is invisible to
    every other check.
    """
    errors: list[str] = []
    for skill in skills:
        where = skill.relative_to(ROOT)
        body, offset = body_of(skill)

        linked: set[str] = set()
        for lineno, line in enumerate(body.splitlines(), start=offset):
            for name, pattern in ROUTES.items():
                if pattern.search(line):
                    errors.append(
                        f"{where}:{lineno}: names the {name} route in the body; "
                        "put the call in references/claude.md, references/omp.md "
                        "or references/codex.md, and name the operation in words "
                        "here"
                    )
            for target in REFERENCE_LINK.findall(line):
                linked.add(target)
                if not (skill.parent / target).is_file():
                    errors.append(
                        f"{where}:{lineno}: links {target}, which does not exist"
                    )

        # The other direction. A reference file nothing links to is a route
        # the session is never sent to read, and it fails nothing else: the
        # skill loads, and reads as complete, with the call unreachable.
        for reference in sorted((skill.parent / "references").glob("*.md")):
            relative = f"references/{reference.name}"
            if relative not in linked:
                errors.append(
                    f"{where}: nothing links {relative}; a reference file the "
                    "body does not point at is never read"
                )
    return errors


def main() -> int:
    errors: list[str] = []

    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    marketplace_path = ROOT / ".claude-plugin" / "marketplace.json"
    marketplace = json.loads(marketplace_path.read_text())

    # The Omp runtime adapter lives in the root package.json (name
    # `daily-driver`), which for Omp is the plugin manifest. It must agree
    # with the Claude plugin manifest and its marketplace entry about the
    # plugin name and version, so one release keeps both harnesses in lock-step
    # (release-please bumps the three of them together via extra-files).
    package_path = ROOT / "package.json"
    if not package_path.exists():
        errors.append("package.json: missing (the Omp runtime adapter's manifest)")
    else:
        package = load_json(package_path, errors)
        if isinstance(package, dict):
            if package.get("name") != plugin["name"]:
                errors.append(
                    f"package.json name is {package.get('name')!r} "
                    f"but plugin.json says {plugin['name']!r}"
                )
            if package.get("version") != plugin["version"]:
                errors.append(
                    f"package.json version is {package.get('version')!r} "
                    f"but plugin.json says {plugin['version']!r}"
                )
            if package.get("version") != marketplace["plugins"][0].get("version"):
                errors.append(
                    f"package.json version is {package.get('version')!r} "
                    "but the marketplace entry says "
                    f"{marketplace['plugins'][0].get('version')!r}"
                )
            omp = package.get("omp")
            if not isinstance(omp, dict) or omp.get("extensions") != ["./extensions/daily-driver.js"]:
                errors.append(
                    "package.json omp.extensions must list exactly "
                    "'./extensions/daily-driver.js'"
                )

    # The marketplace names the repository people install from -- `claude
    # plugin marketplace add jmcvetta/daily-driver` resolves through
    # that name -- so it has to be the repository's. Read from plugin.json's
    # declared `repository` rather than from the checkout directory, which is
    # whatever the person cloning chose to call it.
    repository = stanza.owner_repo(plugin["repository"]).split("/")[-1]
    if marketplace["name"] != repository:
        errors.append(
            f"marketplace.json name is {marketplace['name']!r} "
            f"but plugin.json declares the repository {repository!r}"
        )

    # The plugin is the repository root -- `"source": "./"` -- so exactly one
    # marketplace entry describes it, and it has to agree about the name.
    own = [e for e in marketplace["plugins"] if e.get("source") == "./"]
    if len(own) != 1:
        errors.append(
            "expected exactly one marketplace entry with source './', "
            f"found {len(own)}"
        )
    else:
        # Two independent comparisons rather than an elif chain: a tree that
        # drifted on both reports both, and the maintainer fixes them in one
        # pass instead of learning about the second from the next CI run.
        if own[0]["name"] != plugin["name"]:
            errors.append(
                f"marketplace entry name is {own[0]['name']!r} "
                f"but plugin.json says {plugin['name']!r}"
            )
        # The same sentence is written twice, and each catalog renders a
        # different copy of it: `claude plugin marketplace` lists the
        # marketplace entry, `claude plugin details` reads plugin.json. A
        # drift is therefore visible to users and to nothing else -- both
        # copies stay valid, and neither command shows the other's text.
        if own[0].get("description") != plugin.get("description"):
            errors.append(
                f"marketplace entry description is {own[0].get('description')!r} "
                f"but plugin.json says {plugin.get('description')!r}"
            )

    skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
    if not skills:
        errors.append("no skills/*/SKILL.md found")
    for skill in skills:
        where = skill.relative_to(ROOT)
        fields = frontmatter(skill)
        if fields is None:
            errors.append(f"{where}: no `---` frontmatter block")
            continue
        if fields.get("name") != skill.parent.name:
            errors.append(
                f"{where}: frontmatter name is {fields.get('name')!r} "
                f"but the directory is {skill.parent.name!r}"
            )
        description = fields.get("description", "")
        if not description:
            errors.append(f"{where}: frontmatter description is empty")
        elif len(description) > DESCRIPTION_CAP:
            errors.append(
                f"{where}: description is {len(description)} characters; "
                f"Codex keeps the first {DESCRIPTION_CAP} and cuts the rest "
                "mid-word, so everything past that triggers nothing there"
            )

    # Agents resolve by their frontmatter `name`, not their filename -- the
    # opposite of skills -- so a mismatch means the filename lies, and two
    # agents sharing a name means one of them is unreachable.
    #
    # Zero agents is not an error, unlike zero skills: the plugin ships none
    # today, and `glob` on the absent directory is empty rather than a crash.
    # The loop stays so that an agent revived out of `attic/agents/` is checked
    # the moment it lands.
    agents = sorted((ROOT / "agents").glob("*.md"))
    claimed: dict[str, Path] = {}
    for agent in agents:
        where = agent.relative_to(ROOT)
        fields = frontmatter(agent)
        if fields is None:
            errors.append(f"{where}: no `---` frontmatter block")
            continue
        name = fields.get("name")
        if name != agent.stem:
            errors.append(
                f"{where}: frontmatter name is {name!r} "
                f"but the file is named {agent.stem!r}"
            )
        if not fields.get("description"):
            errors.append(f"{where}: frontmatter description is empty")
        if name:
            if name in claimed:
                errors.append(
                    f"{where}: agent name {name!r} is already claimed by "
                    f"{claimed[name].relative_to(ROOT)}; one of them is "
                    "unreachable"
                )
            else:
                claimed[name] = agent

    errors.extend(reference_errors(skills))
    errors.extend(stanza_errors())

    for error in errors:
        print(f"error: {error}", file=sys.stderr)
    if errors:
        return 1
    print(
        f"manifests agree; {len(skills)} skill(s) "
        f"and {len(agents)} agent(s) checked; "
        "skill bodies are harness-neutral and their reference files are "
        f"linked; every description is inside Codex's {DESCRIPTION_CAP}-"
        "character render; stanza copies agree"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
