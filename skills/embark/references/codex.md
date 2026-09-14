# Codex routes — embark

`SKILL.md` names each operation in words, and this file is where the calls for
a session running in Codex would be. There are none it can make. Claude Code's
routes are in [`claude.md`](claude.md); Omp's, which is a stop like this one,
is [`omp.md`](omp.md).


This skill does not run here
============================

Same answer as Omp, and not the same reason. Omp has no session-opening client.
**Codex has one and this skill cannot reach it.**

Nine tools in the `agent_tasks` namespace, whose own description is *"Manage
Codex tasks available through the connected app server"*, cover most of the
dispatch and the watch:

| Tool | What it would have served |
| ---- | ------------------------- |
| `create_thread` | `Open the sessions` |
| `set_thread_title` | The title each one carries, `session-title`'s form |
| `list_threads`, `list_archived_threads` | Finding the fleet again |
| `read_thread` | `Watch the wave`, reading a task back directly |
| `wait_threads` | `Watch the wave`'s backstop |
| `send_message_to_thread` | `Recover a session`'s correction |
| `set_thread_archived` | `Recover a session`'s retirement |
| `fork_thread` | Nothing this skill needs |

Two of them are better than what Claude Code has. `read_thread` reads back
another task's recent messages and status, which is the thing `claude.md`
records as unavailable there and the whole reason `Watch the wave` watches pull
requests instead. `wait_threads` blocks until up to eight other tasks finish or
need input, which is a watch inside one turn rather than across many.

None of that matters yet, because of the four things below.

**The namespace is terminal-UI only.** It is a dynamic tool namespace served
where that UI is attached to a running app-server daemon, and it is not in the
tool list of a `codex exec` run. A fleet is launched unattended by definition,
and unattended means `codex exec`.

**`create_thread`'s own contract refuses an unasked wave.** It reads *"Create
and start a separate Codex task **only when the user explicitly asks for a new
task**."* `SKILL.md`'s `Waves launch without confirmation` is the opposite
rule, and it is not a rule this skill may quietly drop: it is what `epic`'s one
stop at `Agree the plan` bought. A harness whose dispatch tool asks for the
confirmation `epic` already took is a harness where the two have to be
reconciled deliberately, by somebody, rather than worked around here.

**There is no durable wake.** Nothing in Codex's tool surface schedules a wake
that outlives the turn that armed it. `sleep_tool` is a sleep, which
`review-cycle` forbids outright as a timer rather than a test. `codex queue
--thread <id> --message <text>` injects a message into a saved session and is
the thing to reach for — it needs an external scheduler to fire it, which makes
it a workaround rather than a route, and the constitution says to discuss one
of those before writing it. So
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md)'s never-empty
wake slot has no slot to fill here either, which is the second harness that is
true of.

**The fleet would be one daemon on one machine.** `codex agents` browses
sessions on *"the shared local app-server daemon"*. Every ship is in one
harbour, and the watch that matters runs for hours.


So, on this harness
===================

**Say the skill does not run, name the task issues whose blockers are closed,
and stop** — which is what `omp.md` says, for the reason above rather than for
its reason. That is `epic`'s `Hand off` reached without a fleet, and it leaves
the user holding what they need to put the wave to sea from a harness that can.

Reading the epic to name those tasks is ordinary work and needs nothing from
here: the issue reads go through `gh` in the shell the way Omp's do, and
`issue-deps` has the graph.

**`codex exec` is not the client, and it is the thing to reach for.** It starts
a real agent run from the shell, so a session with a shell can start one per
task. It blocks in the foreground until that run finishes, so a wave of five is
five in series; backgrounded, it reports back to nothing, which is the failure
[`0006`](../../../docs/notes/0006-waiting-for-ci.md) records. Neither shape is
a fleet, and neither survives the session that spawned it.


What would have to become true
==============================

Recorded so that one of these arriving is not read as enough on its own.

1. `agent_tasks` reachable from an unattended run, not only from the terminal
   UI.
2. A dispatch that does not require the user to ask per task, or a decision
   that this skill asks on this harness — which is a change to
   `Waves launch without confirmation` and therefore not one made in passing.
3. A durable wake, for the watch and for the `Keep it current` cadence every
   task session would be holding.
4. A fleet that outlives one local daemon, or a deliberate decision that a
   wave may sink with the machine it was launched from.


Provenance
==========

`codex-cli 0.154.0`, read on 2026-09-12. The subcommands and their flags are
quoted from `--help`; the tool names, their descriptions and the namespace are
read from the installed binary's own tool table. **None of the nine was
driven.** [#181](https://github.com/jmcvetta/daily-driver/issues/181)
established that the terminal UI cannot be reached without credentials, and
that is the wall this file is behind.
