# daily-driver

Daily-driver skills for [Claude Code][cc], [Omp][omp] and [Codex][codex],
packaged as one plugin that all three read.

[cc]: https://claude.com/claude-code
[omp]: https://omp.sh
[codex]: https://github.com/openai/codex

This is one person's working toolkit, published rather than licensed. See
[ANTI-LICENSE.md](ANTI-LICENSE.md) before going further — and then, having
read it, do not go further.

## What's in it

The **constitution** — `rules/constitution.md`, delivered to every session by
hook on Claude Code and Codex, and by the rule provider on Omp — plus **two
runtime adapters that enforce rather than instruct**, `hooks/` for the two
harnesses that run hooks and `extensions/` for the one that does not, and
fourteen skills:

| Skill | What it does |
| ----- | ------------ |
| `pr` | Opens the pull request for the current branch, or brings an open one up to date: branch guard, existing-PR check, draft state. Delegates the title and the body. |
| `pr-title` | The title: concise, and Conventional Commits, which is what release-please reads to decide the next version. |
| `conventional-commits-type` | Picks the type — `fix`, `feat`, `refactor` and the rest — from what the change *does*, never from what the diff looks like. |
| `pr-body` | The body: a one-line summary, a salutation in verse, the `Issues` section that follows it, an executive summary, and engineering detail. |
| `issue-deps` | Records and reads GitHub issue relationships — blocked-by, sub-issue, and which pull request closes what. |
| `issue-labels` | The five labels an issue may carry — `epic`, `task`, `bug`, `proposal`, `research` — and the readiness each one states, which is what decides whether an agent may start unattended. |
| `session-title` | Names the session for the Claude web and mobile lists: forty characters, `#123 shortened issue title` while an issue is in hand. |
| `readme` | Writes a README that answers what this is and how to use it, and nothing else: the shape, the reading of length as a symptom, and the list of what belongs in a commit message, a changelog or `docs/` instead. |
| `judgement-call` | The gate before a choice is put to you: where the correct, standard way already answers it, Claude answers it and says which way it went. A question that survives the gate is asked in the chat reply — the `AskUserQuestion` widget is denied by hook. |
| `review-cycle` | One round on a pull request: the built-in `/code-review`, a verdict on every finding, and the test for whether a later push has earned a second round. |
| `undertake` | Takes a piece of work from its description to a pull request ready for review, opening the issue first where there is none, and keeping the branch current with its base after. |
| `epic` | Breaks work too big for one pull request into task issues under an epic: the two gates that decide there is one, the plan agreed before anything is written, and the waves the sub-issue panel cannot render. |
| `embark` | Works an epic: one Claude session per task issue in the current wave, the muster roll posted to the epic in place of a confirmation, and the watch kept through the pull requests rather than the session client. |
| `deps` | The bulk dependency upgrade: every ecosystem on one branch through the package managers' own bulk commands, green CI as the whole acceptance test, majors reported rather than taken. |

A skill fires on its slash command where it has one, on natural phrasings of
the work, and on the session's own tool calls. The tool-call triggers are
written for all three harnesses, because a `description` is read before any
reference file can be: `pr` fires on Claude Code's
`mcp__github__create_pull_request`, on Omp's `github` tool (`pr_create`) and on
the `gh pr create` that Codex has instead of either, and `judgement-call` on
`AskUserQuestion`, on `ask` and on `request_user_input`. Those are examples
rather than the list — each skill's `description` names its own triggers, and
carries its own register.

**A description has a length budget, and Codex sets it.** Codex's prompt
renderer cuts one at 1021 characters and appends `...`, so the closing
sentences — which are where a description says what must *not* fire it — are
the part that goes. Nothing warns: the skill still loads. `make check` fails a
description over the cap.

The plugin ships no agents. The reviewer panel `review` dispatched went to the
attic with it. [`attic/`](attic/) holds what no longer ships; nothing there is
loaded, and [its README](attic/README.md) says what is kept and why.

## The constitution

`rules/constitution.md` is the always-on layer, in force in every session and
every subagent. Nine sections:

| Section | What it settles |
| ------- | --------------- |
| Voice | Simplified Technical English for prose written in your own voice. |
| Before you reply | A four-line budget on a reply, the two things outside it, and the shape: the answer first, no preamble, no recap. |
| Non-negotiables | Never a production system; dangerous commands in a sandbox or not at all; code without tests is broken; every script named rather than globbed; problems are fixed, never hidden. |
| While you write code | The manual before the web or the source, simplicity, no reinventing a library, no workarounds, correct over quick. |
| When you hit a wall | Stop on the error, re-assess an approach that is failing, ask rather than guess at intent. |
| Before you commit | A doc comment on every new exported symbol, focused commits, message style, named files staged. |
| Before you call it done | The project's own gates decide, not reasoning about them — and CI is where they run, not this machine. |
| Dependencies | Added and pinned through the package manager; never a hand-edited manifest or lockfile. |
| Delegation | Plan first, delegate the implementation, batch the subagents, spend no more quota than the work needs. |

**What belongs there** is the admission test the file states on itself: a rule
lives here only if it changes behaviour in most sessions, hangs off a nameable
moment, and says something the harness does not already say — it is paid for in
every session and every subagent, forever. Amendments are pull requests against
this repository.

**Whether a session got it**: `scripts/check-constitution.py` drives every
injection point, on both harnesses, and asserts they carry the file verbatim
and identically. The
`constitution-reaches-subagent` eval covers the half a script cannot: it asks a
subagent, with every file-reading tool closed, for a phrase only the injected
constitution could have told it.

**Whether it landed**: arriving and being obeyed are different questions, and
the `constitution-reply-is-concise` eval asks the second. It puts a one-line
answer under every pressure to write ten and counts the lines that come back.
`Before you reply` is the rule it measures because that rule's compliance is
countable; the rest of the file needs a judgment about engineering instead.

**How it arrives**: a plugin cannot ship a `CLAUDE.md`, so three injection
points deliver the file — `SessionStart` for the session, and `PreToolUse` on
the `Agent` tool plus `SubagentStart` for every subagent, neither of which
`SessionStart` alone reaches. All three read the one file by exact path and
fail loudly. The measurement behind the second injection point is in [the
planning doc](docs/planning/plugin-replaces-global-memory.md) under R2; the
third is there for Codex, which delegates through `multi_agent_v1` and so has
no `Agent` tool for the matcher to catch.

## The hooks, and the Omp extension

A plugin cannot ship a `CLAUDE.md`, and it cannot ship a preference either. Two
hooks do both jobs on Claude Code and on Codex, and they do them for the same
reason: prose can be read and not followed.

| Hook | Event | What it does |
| ---- | ----- | ------------ |
| `inject-constitution.py` | `SessionStart`, `SubagentStart`, and `PreToolUse` on `Agent`/`Task` | Delivers `rules/constitution.md` to the session and to every subagent. |
| `ask-in-chat.py` | `PreToolUse` on `AskUserQuestion`/`request_user_input` | Denies the multiple-choice widget, and tells Claude to ask the question in the chat reply instead. |

**Codex runs the same two scripts.** Its hook wire contract is Claude Code's —
same stdin, same `hookSpecificOutput` — so `hooks/hooks.json` carries one extra
matcher and one extra event rather than a second copy of anything. The widget
is `request_user_input` there and `AskUserQuestion` does not exist; delegation
goes through `multi_agent_v1`, so `SubagentStart` is the only route a Codex
subagent's constitution can arrive by. Claude Code fires `SubagentStart` too
and honours the same `additionalContext`, so a Claude Code subagent is handed
the constitution twice — the price of one `hooks.json` serving both, since
neither subagent route carries anything that would let it see the other had
fired.

**Why the second one is a hook** and not a skill or a constitution rule: the
preference has no exceptions to weigh, so it should be enforced rather than
instructed, and the constitution's admission test turns it down — most sessions
never reach for the widget, and every session would pay for the rule.
[`docs/notes/0009`](docs/notes/0009-deny-the-question-widget.md) is the
decision, and `judgement-call` is the skill it is ordered with: that gate
decides *whether* to ask, the hook decides *how*.

**Omp has no hook mechanism**, so `extensions/daily-driver.js` does the same
two jobs there: it blocks the `ask` tool with the same wording, and it supplies
the session-title and reminder tools (`daily_driver_set_session_title`,
`daily_driver_schedule`, `daily_driver_cancel_schedule`) that Omp's
`ExtensionAPI` makes natural. The constitution needs no adapter on that side —
Omp's rule provider injects `rules/*.md` carrying `alwaysApply: true`.

**Whether either still fires**: `scripts/check-constitution.py` and
`scripts/check-ask-in-chat.py` run both hooks against synthetic event JSON, and
`scripts/check-omp-extension.mjs` does the same job for the Omp adapter — all
three in `make check`, with `scripts/check-omp-plugin.py` covering discovery
from CI's `omp` job. An adapter that stops firing does not
fail; it silently reverts the behaviour it was installed for, which is the one
failure nothing else would report.

## Layout

The plugin is the repository root — `"source": "./"` in the marketplace
manifest — so there is no nested plugin directory.

```
daily-driver/
├── .claude-plugin/         plugin.json (the version releases bump) and
│                           marketplace.json — the one catalog, read by
│                           `claude plugin install`, `omp plugin install` and
│                           `codex plugin add` alike
├── package.json            the Omp manifest: same name and version, and the
│                           `omp.extensions` entry that loads the adapter
├── attic/                  kept but not shipped; nothing here is loaded
├── rules/constitution.md    always-on rules, one file, read by all three
├── docs/                   how this repository is meant to be used
├── evals/                  the trigger suites, and the constitution's live half
├── extensions/             the Omp runtime adapter
├── hooks/                  the hook adapter, read by Claude Code and Codex:
│                           the constitution's three injection points, and
│                           the deny on the question widget
├── infra/github/           the repository's own settings, as OpenTofu
├── scripts/                the checks CI runs, the stanza, the MCP tally
├── skills/                 one directory per skill in the table above, each
│                           with a references/ file per harness it routes to:
│                           claude.md, omp.md, codex.md
└── template/.claude/       copied into a repository to enable the plugin —
                            a Claude Code file, with no counterpart on the
                            other two
```

**What is shared, and what is per-harness.** The skills, the catalog and
`rules/constitution.md` are one copy each, read by all three harnesses. Two
things are per-harness. The runtime adapter, which is doubled rather than
tripled — `hooks/` serves Claude Code and Codex, whose hook wire contracts are
the same, and `extensions/` serves Omp, which has no hook mechanism at all. And,
inside a skill, the tool routes: a `SKILL.md` says what the skill decides, and
`skills/<name>/references/claude.md`, `references/omp.md` and
`references/codex.md` carry the calls that do it, opened on demand by the
session that needs them. `scripts/check-manifests.py` fails a `SKILL.md` that
names a harness's own routes in its body.

## Installing it

Installation is **per-machine — or, in the cloud, per-environment**. The
plugin's bytes land under the harness's own directory and are read from there;
a repository can point at a plugin, it can never carry one.

On a laptop, two commands, once per machine. For Claude Code:

```sh
claude plugin marketplace add jmcvetta/daily-driver
claude plugin install daily-driver@daily-driver
```

For Omp, the same two commands against the same catalog — Omp reads
`.claude-plugin/marketplace.json` as its Claude-compatible fallback, so there
is one catalog and no second copy to keep in step:

```sh
omp plugin marketplace add jmcvetta/daily-driver
omp plugin install daily-driver@daily-driver
```

`omp plugin list` is what says it took.

For Codex, the same catalog again — it accepts `.claude-plugin/marketplace.json`
as one of its marketplace layouts and `.claude-plugin/plugin.json` as one of its
manifest paths — but **the second verb is `add`, not `install`**:

```sh
codex plugin marketplace add jmcvetta/daily-driver
codex plugin add daily-driver@daily-driver
```

`codex plugin list` is what says it took. Two things about that route are worth
knowing before it surprises you, both measured against `codex-cli` 0.154.0:

- **The install state lives in `$CODEX_HOME/config.toml`**, in a
  `[marketplaces.…]` table and a `[plugins."…"]` one. There is no separate
  install manifest, so a script that rewrites that file uninstalls every plugin
  silently. Append to it.
- **Hooks need persisted trust.** Without it the constitution and the question
  widget's deny are skipped with no warning and no log line — the session looks
  exactly like one running without the plugin. `codex exec` carries
  `--dangerously-bypass-hook-trust` for automation that has already vetted the
  source.

In the cloud — meaning a Claude Code cloud environment, so the Claude Code pair
above rather than either of the others — the same two commands go in the
environment's **Setup script**, which is the one writer that beats the plugin
scan. The environment dialog is behind
the cloud icon above the message box at [claude.ai/code][web].

[web]: https://claude.ai/code

```bash
#!/bin/bash
# CACHEBUST: 1
#
# The environment snapshots itself on this script's text and later sessions
# skip it. Bump the number to reinstall at the current release.
claude plugin marketplace add jmcvetta/daily-driver
claude plugin install --yes daily-driver@daily-driver

# Both commands can return 0 while leaving the plugin uncached, so check
# what the loader actually reads.
grep -qF '"daily-driver@daily-driver"' ~/.claude/plugins/installed_plugins.json &&
  compgen -G ~/.claude/plugins/cache/daily-driver/daily-driver/*/.claude-plugin/plugin.json >/dev/null
```

No `|| true`: a script that exits zero on a failed install snapshots the
failure. Then start a session there and **ask it what it got**, because nothing
announces a plugin that failed to load —

> Without reading any file, say what the constitution tells you about
> production systems. Then list the skills available to you whose names begin
> `daily-driver:`. Then run `ls
> ~/.claude/plugins/cache/daily-driver/daily-driver/`.

Do **not** ask what plugins are installed: that question has a known wrong
answer. After a release, bump the `CACHEBUST` number and ask again — an
existing environment does not pick up a new release on its own.

[docs/bootstrapping-a-repository.md](docs/bootstrapping-a-repository.md) has
the mechanism under all of this, and *the stanza* a repository can carry in
`.claude/settings.json` to say it wants the plugin.

**The stanza is Claude Code's, and `template/` has no Codex counterpart.**
Measured: a project `.codex/config.toml` is not read by this build at all —
`codex doctor` names `$CODEX_HOME/config.toml` as the only config it loaded, and
a marketplace and plugin declared in the project file loaded nothing. So on
Codex there is no repository-level enable of any kind, not even the
record-the-intent one the stanza is on Claude Code; enabling is user-level only,
through the two tables above.

## Portability

The same tree is read by three harnesses. **Claude Code** discovers it as a
plugin. **Omp** reads the Claude-compatible catalog and the same skills, and
adds its own runtime adapter — `extensions/daily-driver.js`, wired by
`omp.extensions` in `package.json`, which brings Omp the behaviour Claude Code
gets from `hooks/`. **Codex** reads the same catalog again and runs `hooks/`
itself: its hook wire contract is Claude Code's — same stdin, same
`hookSpecificOutput`, same `CLAUDE_PLUGIN_ROOT` in a plugin hook's environment
— so it needs no adapter of its own, only the extra matcher and extra event
`hooks/hooks.json` already carries.

**For local development, `omp --plugin-dir <path>`.** It loads the skills
straight from a checkout, with nothing installed. It does **not** load the
extension: an extension entry point is read from an *installed* plugin's
manifest, and a `--plugin-dir` root is never installed. So the `ask` deny and
the `daily_driver_*` tools are absent on that route — edit a skill with it,
and install (or `omp plugin link .`) to exercise the adapter. Measured on omp
18.1.17, and `scripts/check-omp-plugin.py` is what keeps it measured.

**Codex's own gaps are recorded rather than worked around.** It has no
`mcp__github__*` server and no `github` tool, so GitHub goes through `gh` in the
shell, the way it does on Omp. It has no durable wake and nothing that blocks on
a check, so `review-cycle` cannot wait and `undertake`'s `Keep it current`
cadence stops at `Ready for review`. It has no session client an unattended run
can reach, so `session-title` and `embark` say so instead of guessing. Each of
those is written in the skill's own `references/codex.md`, with what would have
to become true for it to change.

One tree, one release, and a runtime adapter per hook mechanism rather than per
harness. Where a rule holds on only some of them,
[`docs/notes/0011`](docs/notes/0011-two-harnesses-one-skill-tree.md) and
[`0016`](docs/notes/0016-three-harnesses-one-skill-tree.md) are the decisions:
`0011` says why there is one skill tree, where a harness route lives, and which
rules are Claude Code only — among them the never-empty wake slot, since neither
Omp nor Codex has a timer that outlives its session — and `0016` says what the
third harness changed about all of that.

## Checks

`make check` is what CI runs — the same target, not a restatement of it. It
runs `claude plugin validate --strict` over the manifests and the skills — and
over `agents/`, on the runs where the plugin ships any; `shellcheck` over every
shell script; `scripts/check-manifests.py` for what `validate` lets through,
such as a skill whose frontmatter `name` disagrees with its directory; `scripts/check-constitution.py`, which drives
both hooks against synthetic event JSON and asserts the constitution comes back
from each; `scripts/check-labels.py`, which asserts the issue-label standard
says the same thing in `issue-labels` and in the OpenTofu that declares it;
`scripts/check-eval-fixtures.sh`; `scripts/check-omp-agent.py`, which drives
the Omp eval arm's frame reduction against recorded frames;
`scripts/check-codex-agent.py`, which asserts the Codex arm renders the judge's
anchor byte-identically to the Omp arm's; and `scripts/check-eval-arms.py`,
which keeps the Claude, Omp and Codex thirds of the forked eval rows in step —
and the Makefile's three run targets in step with them.

**One of its legs is Omp's.** `scripts/check-omp-extension.mjs` imports the
adapter under Node with a faked `ExtensionAPI` and asserts the `ask` deny and
the three tools behave. It needs only Node, so it runs everywhere the rest of
`check` does.

Three more checks are deliberately outside it. `make check-omp-plugin` starts a
real `omp --mode rpc` and asks the running agent what it got: every skill
offered as a `skill:<name>` command on the `--plugin-dir` route and again on
the installed route, `omp plugin list` reporting the plugin after `omp plugin
link .`, and the extension loading rather than failing silently. It is
credential-free and calls no model, against a throwaway `HOME` — but it needs
Omp installed, which `make check` must not start requiring of a laptop that is
only editing a skill. CI's `omp` job runs it instead, gated on the files that
can actually break the integration — `package.json`, `.claude-plugin/`,
`extensions/`, and the check itself. That job reports into `CI Success`
whether or not the gate opens, so a broken Omp integration blocks a merge; its
comment says why each file is on the list, and why `skills/` is not.
`make check-infra` parses the OpenTofu
stack — see [infra/github/README.md](infra/github/README.md). `make evals-run` — and `make evals-run-omp` and
`make evals-run-codex`, the same suites on the second and third harnesses —
needs a live model, and CI here is
credential-free — see [evals/README.md](evals/README.md); `TASKS='tasks/constitution/*.yaml'` is the
other half of the constitution's test, since only a real session can prove the
harness honours the subagent hook. Those rows carry `skip:codex`: the Codex arm
links skills and installs no hooks, so the constitution never reaches that
session and both rows would score zero for a reason that is not the
constitution's.

`make mcp-usage` is not a check. It counts which GitHub MCP tools this laptop
called, so the server's `--toolsets` list can be narrowed on evidence; see
[docs/github-mcp.md](docs/github-mcp.md).

## Releases

release-please cuts them from the Conventional Commit type in a merged pull
request's **title**, which squash-merge makes the commit subject. It bumps
`version` in `.claude-plugin/plugin.json` and the matching field on the
marketplace entry together — `claude plugin validate --strict` fails when
those two disagree. Each pull request gets a comment saying which tags merging
it would cut, from [projected-releases-action][pra].

`bump-minor-pre-major` is on, so below `1.0.0` a breaking change bumps the
minor rather than the major. Nothing reaches `1.0.0` on its own: it takes an
explicit `Release-As: 1.0.0` trailer, which makes the first stable release a
decision someone makes rather than one the next `!` confers.

**That trailer goes in the squash-commit message, edited at the merge box,
and nothing may follow it.** release-please reads the note out of the commit
subject and body, and voids it where non-trailer text sits below — which a
pull request body always has here, since `pr-body` ends one with engineering
detail and the attribution lines land under that. A voided note is silent:
the version comes out as the arithmetic says and nothing logs a reason.

[pra]: https://github.com/jmcvetta/projected-releases-action

## Don't install this

Genuinely: write your own. This fits its author the way a worn boot fits a
foot, and you have different feet.

If you disregard that, the mechanics are ordinary and the consequences are
enumerated at length in [ANTI-LICENSE.md](ANTI-LICENSE.md).
