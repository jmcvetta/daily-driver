# Three harnesses, one skill tree

**Status:** decided, 2026-09-12.
**Provenance:** decided across
[#180](https://github.com/jmcvetta/daily-driver/issues/180) and its
children, as each part was built. This note records those decisions after the
fact, in one place, the way [`0011`](0011-two-harnesses-one-skill-tree.md)
recorded the ones spread over #148.
**Resolves:** [#186](https://github.com/jmcvetta/daily-driver/issues/186).
**Extends:** [`0011`](0011-two-harnesses-one-skill-tree.md), which made the tree
portable and set the shape this follows.
**Amends:** [`0011`](0011-two-harnesses-one-skill-tree.md) in two places, marked
below.

`0011` answered how much of the tree is allowed to know which harness is reading
it, with two harnesses in view. Codex (`codex`) is the third, it reads Claude
Code plugins natively, and #181 measured what that means against a running
`codex-cli` 0.154.0 rather than against the source. The answers are here.

[`0015`](0015-the-codex-arm.md) is the other half of the epic and is not
restated here: it records the eval arm, from #185, extending
[`0013`](0013-the-omp-arm.md) as this note extends `0011`. #186 asked for one
note and named `0015`; `0015` was already written, to a different subject and a
different provenance, so this is a second note rather than an edit of that one.

## Decided

**One catalog still, and two runtime adapters rather than three.** Codex accepts
`.claude-plugin/marketplace.json` as a marketplace layout and
`.claude-plugin/plugin.json` as a manifest path, both confirmed against the
binary, so there is no `.codex-plugin/` copy — the same reasoning `0011` used to
refuse an `.omp-plugin/` one. The adapter is doubled rather than tripled for a
stronger reason: Codex's hook wire contract *is* Claude Code's. Same stdin, same
`hookSpecificOutput.additionalContext`, same `CLAUDE_PLUGIN_ROOT` exported to a
plugin hook, and `hooks/hooks.json` discovered with no manifest declaration. So
`hooks/` serves both, and `extensions/daily-driver.js` serves the one harness
with no hook mechanism at all.

What Codex cost `hooks.json` is one extra matcher and one extra event, not a
second copy of anything.

**The question widget is `request_user_input`, and matching it was not enough.**
`AskUserQuestion` does not occur anywhere in the Codex binary, so
`^AskUserQuestion$` could never fire there. The matcher is now
`^(AskUserQuestion|request_user_input)$`, one entry rather than two so that
exactly one handler runs. `ask-in-chat.py` had let through any event naming a
tool other than `AskUserQuestion` — which is precisely what a
`request_user_input` event is — so it carries both names, and the denial reason
names both.

Codex narrows the widget on its own besides: its own description says Plan mode
only, and the binary refuses it outright in exec mode. An unattended run cannot
reach it whether or not the adapter denies it. The deny is still written:
[`0009`](0009-deny-the-question-widget.md)'s reasoning is about the preference
rather than about reachability.

**`SubagentStart` is the constitution's third injection point.** Codex delegates
through the `multi_agent_v1` namespace and has no `Agent` tool, so the
`PreToolUse` matcher `^(Agent|Task)$` reaches no Codex subagent. `SubagentStart`
is the only route left. `session-start` and `subagent-start` differ only in the
event name they echo and share one renderer: two copies would be two texts to
keep equal, and the equality is the whole point.

*The duplicate on Claude Code is deliberate.* Claude Code fires `SubagentStart`
too and honours the same `additionalContext`, so a Claude Code subagent now
receives the constitution twice — once from `pre-tool-use`, once from
`subagent-start`. Neither event carries anything that would let it see the other
had fired, so suppressing one would mean sniffing the harness. The duplicate is
the price of one `hooks.json` serving both, and it is paid rather than hidden.

**A handler must echo the exact `hookEventName` it was sent.** Codex rejects the
output otherwise — `SessionStart Failed` — and drops the `additionalContext`
silently. Nothing here had to change; it is a constraint on anything new.

**A `description` is capped at 1021 characters, and the cap is Codex's
renderer.** The parser has none; the prompt renderer cuts mid-word and appends
`...`. `undertake` (1353), `epic` (1197), `review-cycle` (1162) and `deps`
(1034) were all being cut, and the cut lands on the closing sentences, which are
where a description says what must **not** fire it — `undertake` lost that
sentence entirely. `scripts/check-manifests.py` now fails a description over the
cap.

This is the one place the third harness constrains the shared half of the tree,
and it does so because a `description` is the trigger: it is read before any
reference file can be, so it cannot be forked per harness the way a route can.

*No skill is excused.* The cut is a property of the renderer rather than of a
skill's routes, so a check that exempted the one skill failing it would not be a
check.

**Codex's routes are Omp's `gh` routes, forked where a Codex fact forces it.**
There is no `mcp__github__*` server and no built-in `github` tool, so GitHub goes
through the shell. Each of the twelve skills that routes anywhere now carries a
`references/codex.md`, and `check-manifests.py` knows Codex's call names, so a
Codex route written back into a `SKILL.md` body fails the same way a Claude Code
one does. **This amends `0011`**, whose split named two reference files; it names
three.

Four skills differ from their Omp sibling on a measured Codex fact rather than on
taste: `pr-body` prescribes `gh pr edit --body-file` where Omp names `--body`;
`issue-deps` has two clients rather than three, since the MCP branch of its probe
does not exist; `judgement-call`'s widget is `request_user_input`; and `epic`
can read neither a session nor the running model, so the `Model:` line is written
from a table or not at all.

**A stop is a route.** Three skills resolve to *nothing to call* on Codex, and
each says so in its own file rather than degrading quietly:

- **`session-title`** — `set_thread_title` exists, and is a dynamic tool of the
  terminal UI served only where that UI is attached to a running app-server. It
  is absent from a `codex exec` run, which is what an unattended run is. There is
  no shell fallback: `codex` addresses a session by name in `queue`, `archive`,
  `delete` and `resume`, and has no subcommand that sets one.
- **`embark`** — Codex has a session client this skill still cannot use.
  `create_thread`'s own contract reads *"Create and start a separate Codex task
  only when the user explicitly asks for a new task"*, which is the exact
  opposite of `Waves launch without confirmation`. Reconciling those is a
  decision, not a workaround to write here.
- **`review-cycle`'s wait** — `codex exec review --base <branch>` is real,
  non-interactive and shell-reachable, but it reviews the checkout rather than a
  pull request, takes no effort level, and posts nothing; and nothing on this
  harness blocks on a check or wakes a session after the turn ends. Codex is the
  first harness under the clause *a surface that can neither block nor wake
  itself cannot wait*, which until now had none.

`0011` set this shape when it made
[`0010`](0010-the-wake-slot-is-never-empty.md)'s never-empty wake slot Claude
Code only rather than softening it for Omp. **That amendment now holds against two
harnesses rather than one**: neither Omp nor Codex has a timer that outlives its
session, so `undertake`'s `Keep it current` cadence stops at `Ready for review`
on both.

**Nothing in a repository enables the plugin on Codex.** Install state lives in
`$CODEX_HOME/config.toml`, in a `[marketplaces.…]` table and a `[plugins."…"]`
one, with no separate install manifest — so a script that rewrites that file
uninstalls every plugin silently, and must append. A project `.codex/config.toml`
is **not read at all** by this build: `codex doctor` names the user file as the
only config it loaded, and a marketplace and plugin declared in a project file
loaded nothing.

So `template/.claude/settings.json` gets no Codex counterpart. There is nothing
to template — not even the record-the-intent value the stanza has on Claude Code,
which `docs/bootstrapping-a-repository.md` already measures as neither necessary
nor sufficient there.

**The install verb is `add`.** `codex plugin marketplace add` matches Claude
Code's spelling; `codex plugin install` does not exist, and the second command is
`codex plugin add daily-driver@daily-driver`.

## Known limits, recorded rather than fixed

**Hook trust is a silent gate.** With no trust persisted, Codex runs no hook and
says nothing — no warning, no log line, no output — so a session with the plugin
installed and untrusted hooks is indistinguishable from one without the plugin.
That is the failure mode `docs/bootstrapping-a-repository.md` exists for,
arriving through a second door. `codex exec --dangerously-bypass-hook-trust` is
the documented escape hatch for automation that has already vetted its sources.

**The subagent route is reasoned, not driven.** #181 could not reach the
delegation path: the stub router rejected every spelling of `spawn_agent`, and
`multi_agent_v2` is not stable. `SubagentStart` and `SubagentStop` were never
observed to fire on Codex. This costs little — `subagent-start` reads no part of
its event, so there is no shape to get wrong — but whether Codex fires the event
at all is the one link in the constitution's third injection point that has not
been measured. `tasks/constitution/*` carries `skip:codex` for an unrelated
reason ([`0015`](0015-the-codex-arm.md)), so the eval arm does not close this
either. A live Codex session with credentials is what would.

**`skill://` is not how a skill is engaged here.** The binary carries a
`UserInput::Skill` variant, but a plain-text `codex exec` prompt of
`skill://daily-driver:pr` reached the model as that literal text. What Codex
actually does is hand the model a skills table in a developer message and let it
open `SKILL.md` with an ordinary shell call. Whether a structured skill mention
works from the terminal UI is untested, and the UI needs credentials.

**No route here has been driven against an account.** Every Codex fact in this
note comes from `codex exec` against a stub Responses API, from `--help`, or from
the installed binary's own tool table. No `agent_tasks` tool was called and no
review was run.
