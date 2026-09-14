# Codex routes — embark

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in [`claude.md`](claude.md);
Omp's — the same fallback, on a surface measured further — is
[`omp.md`](omp.md).


Why the web route has no calls here
===================================

The recorded facts stand, and they are now the reason the fallback runs
rather than the reason the skill stops.

**Codex has a session-opening client this skill cannot reach.** Nine tools in
the `agent_tasks` namespace, whose own description is *"Manage Codex tasks
available through the connected app server"*, cover most of the dispatch and
the watch: `create_thread` for `Open the sessions`, `set_thread_title` for
the title each one carries, `read_thread` and `wait_threads` for the watch,
`send_message_to_thread` and `set_thread_archived` for `Recover a session`.
None of that matters, because:

- **The namespace is terminal-UI only.** It is served where that UI is
  attached to a running app-server daemon, and it is not in the tool list of
  a `codex exec` run. A fleet is launched unattended by definition, and
  unattended means `codex exec`.
- **`create_thread`'s own contract refuses an unasked wave.** It reads
  *"Create and start a separate Codex task **only when the user explicitly
  asks for a new task**."* `SKILL.md`'s `Waves launch without confirmation` is
  the opposite rule, and reconciling the two is a deliberate change to that
  section, not a route written in passing.
- **The fleet would be one daemon on one machine.** `codex agents` browses
  sessions on *"the shared local app-server daemon"*, and every ship would be
  in one harbour.

So `Open the sessions` takes the harness-local subagent fallback on this
harness, and the delegation surface is **`multi_agent_v1`** — the namespace
[`0016`](../../../docs/notes/0016-three-harnesses-one-skill-tree.md) records
as how Codex delegates, and the one the constitution's `SubagentStart` hook
exists to reach.

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the sessions` | Dispatch one implementor per task, concurrently | `multi_agent_v1`, one delegation per task issue in a single wave |
| `Post the muster roll` | Comment on the epic | `gh issue comment <number> --body-file <path>` |
| `Post the muster roll` | Mark the wave in the epic's body | `gh issue edit <number> --body-file <path>` |

Each delegation's prompt is the task issue number and the instruction to
undertake it, and nothing else. Duplicate-dispatch protection is unchanged:
the epic's muster rolls and each task issue's claim comments are read before
the wave is built, exactly as `Take the wave` words it, and a delegation that
fails to launch is reported while the rest of the wave sails.

Until the namespace is driven, the delegation operation and its batch
semantics cannot be named more concretely than this. A Codex session that
cannot resolve them at run time stops at `Open the sessions` and says so —
a stop at dispatch, with the wave named, not a declaration that the skill
does not run.


What this surface has not been measured to do
=============================================

**The namespace has never been driven.** [#181](https://github.com/jmcvetta/daily-driver/issues/181)
could not reach the delegation path — a stub router rejected every spelling
of `spawn_agent`, and `multi_agent_v2` is not stable — so this file specifies
the fallback against the namespace rather than against its tools, and the
provenance below records it. Three things in particular are unmeasured, and
each is written the way the round should read it:

- **A model argument.** No delegation argument is measured to select a model.
  The cheaper default of `Open the sessions` is therefore expressed as the
  delegation's default implementor, and the model an implementor actually ran
  on is read back from what the harness reports of that subagent where it
  reports one, never recalled; where nothing reports it, the muster-roll row
  records the implementor's agent type and marks the model unreported — a
  guessed identifier is not a measurement. The task issue's `Model:` line is
  advisory, the bypass is the orchestrator's judgement, and `SKILL.md`'s
  wording is the rule this file does not restate.
- **Agent-to-agent messaging.** Whether a delegated implementor can send a
  question back to the delegating session is not measured. The route this
  file specifies is `SKILL.md`'s: the advisor is the orchestrator itself, and
  an implementor's question travels by whatever messaging the namespace
  carries. Until the namespace is driven, a fallback wave is supervised by
  the orchestrator reading the delegations' reported state and the pulls —
  and a question that could not travel is caught there. That catch is the
  second reason the strong-model review exists, so a silent implementor is
  the review's finding even where the messaging fails.
- **A wait.** No durable wake exists on Codex, measured in `review-cycle`'s
  [`codex.md`](../../review-cycle/references/codex.md) and unchanged by the
  fallback: `sleep_tool` is still a sleep, and a wake built on `at` or cron is
  still a workaround. The wave is supervised through the delegation lifecycle
  where the namespace offers a wait; where the turn must end with ships still
  out, the pulls are the next watcher's entry, and that is said once rather
  than claimed.


The strong-model review
=======================

At each implementor's ready gate, the round is run by a strong model — the
orchestrator or the shared advisor, never the implementor. The implementor
hands its head over the messaging where the namespace carries one, and
waits; the surface is
`review-cycle`'s own [`codex.md`](../../review-cycle/references/codex.md):
`codex exec review --base <branch>`, which starts a fresh session with its own
model — that is what makes it a named surface rather than a bare subagent,
and why the round runs it once per diff rather than once per push.


What would have to become true
==============================

1. `agent_tasks` reachable from an unattended run — which would make the
   web-session route the road back, not the fallback.
2. A durable wake, for the watch and for the `Keep it current` cadence every
   implementor would be holding.
3. The delegation namespace driven: its tool names, a model argument, and an
   agent-to-agent messaging route measured. #181's wall stands until then.
4. A fleet that outlives one local daemon, or a deliberate decision that a
   wave may sink with the machine it was launched from.


Provenance
==========

`codex-cli 0.154.0`, read on 2026-09-12; the `agent_tasks` table, its
terminal-UI-only finding, and `sleep_tool` are from that reading. **The
delegation namespace has never been driven**:
[#181](https://github.com/jmcvetta/daily-driver/issues/181) established that
the delegation path could not be reached from the eval harness, and nothing
since has measured it. This file specifies the fallback against the namespace
rather than against its tools for that reason.
