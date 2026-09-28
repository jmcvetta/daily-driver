---
name: stand-down
description: >-
  This skill should be used whenever an embarked epic's watch is ended
  because work must stop — when the user says "/stand-down", "stand down",
  "stop work", "wrap up", or is putting the machine away, and whenever an
  embark must end for any reason short of the last wave coming in. Supplies
  the wrap-up that secures every implementor's work-in-progress — commit and
  push — before the handoff it writes: one comment per task issue at sea and
  one roll-shaped stand-down comment on the epic. Then the stop and archive
  of every implementor, the cancellation of the orchestrator's own watches,
  and the banner that says stopping is safe. Runs fast by design: parallel
  batches, no polls, one bounded wrap-up wait, one bounded retry anywhere.
  Not for the watch ending because the epic is worked out — `embark` reports
  that itself — and not for a single issue, which has no fleet to stand
  down.
---

# Stand-down

An embark in progress, a stopped fleet out, and a handoff that lets the next
session pick the work up. `embark` dispatches a fleet per epic and watches it
through GitHub; this skill is what ends that watch when the user must stop —
the laptop going to sleep is the common case — before the last wave has come
in.

It is an orchestrator, in the same shape as `embark`: **it invokes, it does
not restate**. What the fleet is, how it was dispatched, and how a
replacement is opened are `embark`'s; the muster-roll format and the
latest-entry-wins read are `embark`'s; the epic's body states are `epic`'s;
the graph reads are `issue-deps`'; the model, harness and session record
every write carries is `provenance`'s. What this skill owns is the ending:
the wrap-up that secures the work, the handoff record, the stop and archive,
the watch cancellations, and the banner.

**Speed is the design constraint, amended by one wait.** The user asked to
stop, not to orchestrate a stop. The steps below run in parallel batches,
never poll for confirmation, and allow one bounded retry anywhere. The one
exception is `Secure the work`'s wrap-up wait, bounded by a single shared
deadline for the whole fleet — the only wait this skill takes, and never an
answer awaited from an implementor: messaging here is one way, and what the
wait watches for is a turn ending, not a reply. Anything slower than that is
a residual the banner reports, never a further wait.

**The routes are per harness, and they live beside this file.** Every call
the steps below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before `Read the fleet`. Where a surface has no primitive a
step needs, its file says so in words — silence would read as oversight.

**Every step has a name, and the name is how it is cited.**
[`0005`](../../docs/notes/0005-steps-are-cited-by-name.md) is the decision
and `scripts/check-step-names.py` is what enforces it.


The sequence
============

| # | Step | Owner |
| - | ---- | ----- |
| 0 | `Read the fleet` | this skill, `embark` |
| 1 | `Secure the work` | this skill |
| 2 | `Write the handoff` | this skill |
| 3 | `Stop the fleet` | this skill |
| 4 | `Cancel the watches` | this skill |
| 5 | `Print the banner` | this skill |

0 — Read the fleet
------------------

The record decides what is at sea, never a session status.

Read the epic's comments — **all the muster rolls, not only the latest** —
and every task issue a roll names, read at its claim comments and any
handoff a previous stand-down left. Read the landing mode from the latest
record that carries it. A task is at sea when the latest entry for it names
a live implementor; a row already marked retired, and an implementor the
harness reports as finished or failed, are not the fleet. On the
harness-local fallback, the dispatch handles the orchestrator holds are the
second half of the read — but the GitHub record is what outlives them, and a
stand-down asked of a cold session, its dispatch handles gone, works from the
record alone.

The reads run in one parallel batch. No full comment histories are paged:
the rolls and the claims carry what this step needs.

**No epic, or an epic with nothing at sea, is not an error.** `Print the
banner` runs immediately, with the count of what was stood down at zero and
the reason named — the invocation is a stop instruction, and the answer to
it is the stop.

1 — Secure the work
-------------------

Before the handoff is written, so its branch line describes what actually
reached origin rather than what an implementor merely held. Runs in one
parallel batch across the fleet — one wrap-up per web session, one
cancel-then-commit per harness-local subagent — and nothing here waits on
more than the one deadline below.

**Web sessions (Claude Code).** Interrupt the session, then address it the
way `embark`'s `Recover a session` addresses a correction — the muster
roll's already-resolved name where `Read the fleet` carries one, otherwise
`ListAgents` — with the wrap-up, sent by `SendMessage` to that name: commit
everything in progress to the task branch, push it, and end the turn without
starting anything else. Then wait, on one shared deadline for the whole
fleet, until every session's turn has ended or the deadline passes; the
reference file names the read and the deadline. Leaving that wait is not
itself securing: a session the deadline outlasts, a session no name can
reach at all, and a session whose turn ends in error before its push
completes are all archived anyway at `Stop the fleet` and reported as a
residual in the banner, by name — securing its work was attempted, not
guaranteed.

**Harness-local subagents (Omp, Codex).** Cancel the subagent first, by its
dispatch handle, exactly as `Stop the fleet` always has, then this session
itself — not the subagent — commits the work in progress in that worktree
and pushes its branch, on the same best-effort footing as the cancel: an
unconfirmed cancel does not guarantee the subagent has stopped writing, so a
collision is possible in the narrow window between the two, and a git
failure from it is a residual like any other. No wait is needed: the commit
and push are this session's own calls, not another implementor's turn to
finish.

**The work-in-progress commit**, on every harness: it lands on the task's
existing feature branch, never a new one. Its message marks it plainly as
unfinished work from a stand-down. It stages named files — the constitution's
rule against `git add -A` and `git add .` holds here too — and it skips no
hook and no test. It opens no pull request and marks nothing ready. A branch
with nothing to commit is pushed as is, so origin carries whatever was
already committed even where this step adds nothing new.

**A worktree, or a session, that cannot be committed or pushed is a
residual.** Named in the banner, the same as any other; nothing here retries
past the one bounded attempt.

2 — Write the handoff
---------------------

After the work is secured, so the record describes the pushed tip rather
than a tip about to move. **Template fill only**: the handoff is written
from the record and the harness's issue and pull-request state, never from
what an implementor could be asked — no implementor is messaged for a
summary, because the answer is a wait and this skill has none. The one
message this skill does send is `Secure the work`'s wrap-up instruction, and
it asks for a commit and a push, never for a summary or an answer.

**One handoff comment per task issue at sea**, in this shape:

```markdown
## Handoff — fleet stood down <UTC timestamp>

Implementor `<id>` (<session|subagent>) was retired by stand-down. The work
is yours to reclaim.

- Branch: `<branch>` — <link>. The origin tip is authoritative as of this
  comment.
- Pull request: <#N and state, or "none open">.
- Worktree (this machine): <path, or "none">.
- Secured: <yes — work in progress was committed and pushed before the stop
  | no — residual, see the stand-down comment on the epic>.

Work in progress was committed and pushed to the branch above before this
implementor was retired, where securing it succeeded — the origin tip is
what it left, not what a cloud workspace held. Where it did not, "Secured:
no" says so, and nothing beyond the last push survived.
```

This comment ends with `provenance`'s block, and the stand-down comment below
carries it just before its envoi. Both blocks name this stand-down session
rather than any retired implementor's.

**One stand-down comment on the epic**, shaped like a muster roll with its
rows marked retired. What the retired rows buy is honesty in the epic's
latest record: a resumed `embark` reads that the named implementors no
longer exist, instead of steering or re-reading sessions that are gone. The
claims on the task issues still read at sea, so the resume converges
through `Recover a session`, which reopens each quiet task on the branch
its claim comment or pull request names:

```markdown
## Stand-down — <UTC timestamp>

The watch was ended at the user's instruction. Every implementor below was
retired; a row marked retired names an implementor that no longer exists.
This comment supersedes the muster rolls above it.

Landing: <orchestrator|by hand>

| Task | Implementor | State at the stop |
| ---- | ----------- | ----------------- |
| #144 — Validate against the schema. | `session_01AbC…` — retired | branch `…`, PR #… open, unmerged |

Watches retired with this session: <timer ids>, <watcher names>,
<subscriptions>.

Each task issue carries its own handoff. Resume: run `/embark` — it reads
the muster rolls and this comment, watches the tasks still open, and
recovers each quiet task by reopening on the branch its claim or pull
request names.
```

**The stand-down comment ends with an envoi**: a brief farewell stanza for
the watch, after `provenance`'s block, each line italicised as
[`HAIKU.md`](../../HAIKU.md) shows. It is last so the rows and the resume
line are found first. The handoff comments on the task issues carry none:
each hands work to whoever reclaims it, and verse never attaches to a write
somebody has to act on.

The landing mode is copied unchanged from the latest record into this
superseding comment. A resumed `embark` therefore reads the same opt-out or
default after every earlier muster roll has been superseded.

The epic's body is **not** edited. `epic`'s wave states are `in progress`
and `done` and nothing else — a third state invented here is one `epic`'s
body fill would erase, and the stand-down comment is the record, not a body
state. A wave left at sea still reads `in progress` in the body; what
changed is on the epic's comments, which is where `Take the wave` reads
at-sea status from.

**Idempotent re-entry.** A stand-down interrupted by a session death is
re-run, not duplicated, and the writes are idempotent one by one: a handoff
comment already on a task issue is not posted twice, and a stand-down
comment already on the epic is not posted again. `Write the handoff` writes
only what is missing, and a record that is complete sends this step
straight to the stops.

3 — Stop the fleet
------------------

Everything in one parallel batch, and nothing polled beyond `Secure the
work`'s one bounded wait, already spent by the time this step runs.

**A web session is archived.** It was already interrupted and sent its
wrap-up at `Secure the work`; this step is the archive alone. It runs
whether that session's turn ended inside the deadline or not — a session the
deadline outlasted was already named a residual there, and archiving it here
does not undo that naming. If the archive call rejects a session it believes
is still running, one retry after the interruption's result is in; a second
refusal is reported as a residual, not retried in a loop.

**A harness-local subagent was already cancelled at `Secure the work`**,
along with the commit and the push into its worktree. There is nothing left
to stop here: this step is a no-op for that fleet member, and the handoff
already named its branch and worktree path.

Nothing is stopped without first being told to push and given a bounded
chance to: that is `Secure the work`'s job, done before this step runs. What
survives an implementor that missed its wrap-up window is exactly what
reached origin by then — named as a residual, never softened into an
accepted loss.

4 — Cancel the watches
----------------------

Fire-and-forget, by the identifiers the record holds, in one parallel
batch: the backstop timer behind the wake slot, any persistent watcher a
CI wait left running, and every pull-request subscription the watch
subscribed. Their identifiers go in the epic's stand-down comment —
written there at `Write the handoff`, when they are known — so a reader
can see what was silenced as well as what was stopped.

A cancel that fails is a residual for the banner, not a wait. The
orchestrator's own session ends at the banner regardless: no wake is
re-armed, and no check-in restarted.

5 — Print the banner
--------------------

After the stops and the cancels have **returned** — not after they are
confirmed. The banner is the answer to the invocation, and it is printed
even where nothing was at sea, where the handoff failed to post, or where
residuals remain:

```
==================================================================
 STAND-DOWN COMPLETE — SAFE TO STOP
 Stopped: 5 implementors (3 archived, 2 cancelled) · Secured: 5 of 5
 Residuals: none · record: <epic URL>
 Resume: /embark
==================================================================
```

Residuals are listed, one line each, never silent: an implementor whose work
could not be secured — the wrap-up deadline passed, no name could reach it,
its turn ended in error before the push completed, or a worktree would not
commit or push — an implementor that could not be stopped, a comment that
failed to post, or a watch that could not be
cancelled. **A handoff that failed to post never blocks the stops**
— a lost record is better than a fleet left running — and the banner says
the record gap by name. The session ends after the banner: nothing is
re-armed, and the next turn on this work is a resumed `embark`.


Where it stops and waits
========================

Nowhere, by design, past the one bounded wait `Secure the work` takes for
the wrap-up. The invocation is a stop instruction, and every stop below it
runs through: no permission is asked to secure, to comment, to archive, to
cancel, or to print the banner. The two things that look like stops are
reports instead:

- **Nothing is at sea** — at `Read the fleet`. The banner prints with a
  zero count and the reason; if the invocation named an issue that is not
  an embarked epic, the report says which skill takes it — `undertake` for
  a task issue, `embark` for an epic still to work.
- **A residual** — at `Print the banner`. Named in the banner, one line
  each, and left for the person reading it. Nothing here retries a
  residual twice.

Past the wrap-up, the one wait this skill never takes is the one `embark`'s
own ends take: `Close the epic` is `embark`'s, and a stand-down is not asked
for when the last wave comes in.


Non-goals
=========

- **Does not merge, review, or close anything.** The pull requests stand
  where they stood; a resumed `embark` applies its recorded landing mode.
- **Does not edit the epic's body.** No third wave state, no wave marked
  anything — the stand-down comment is the record.
- **Does not re-dispatch.** The resume is `embark`'s: a resumed watch finds
  each task quiet and reaches `Recover a session`, which reopens on the
  branch the claim comment or pull request names. The replacement session
  reaches the handoff through `undertake`'s read of its issue's comments,
  not through `Recover a session` itself.
- **Does not ask the fleet anything.** `Secure the work`'s one message per
  web-session implementor is an instruction, not a question — it asks for a
  commit and a push, and this skill never reads a reply to it. A correction
  or a request for a summary is a different kind of message, one that waits
  for an answer, and the handoff is written from the record instead.
- **Does not fire on a worked-out epic.** `Close the epic` ends an embark that
  succeeded; this skill ends one that was interrupted.
- **Does not fire on a single issue.** One `undertake` has no fleet; the
  session holding it can simply stop, and its claim comment is already the
  record.
