---
name: stand-down
description: >-
  This skill should be used whenever an embarked epic's watch is ended
  because work must stop — when the user says "/stand-down", "stand down",
  "stop work", "wrap up", or is putting the machine away, and whenever an
  embark must end for any reason short of the last wave coming in. Supplies
  the handoff it writes before anything stops — one comment per task issue
  at sea and one roll-shaped stand-down comment on the epic — the stop and
  archive of every implementor, the cancellation of the orchestrator's own
  watches, and the banner that says stopping is safe. Runs fast by design:
  parallel batches, no polls, no waits, one bounded retry anywhere. Not for
  the watch ending because the epic is worked out — `embark` reports that
  itself — and not for a single issue, which has no fleet to stand down.
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
the graph reads are `issue-deps`'. What this skill owns is the ending: the
handoff record, the stop and archive, the watch cancellations, and the
banner.

**Speed is the design constraint.** The user asked to stop, not to
orchestrate a stop. The steps below run in parallel batches, never poll for
confirmation, await no answer from any implementor, and allow one bounded
retry anywhere. Anything slower than the stops themselves is a residual the
banner reports, never a wait.

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
| 1 | `Write the handoff` | this skill |
| 2 | `Stop the fleet` | this skill |
| 3 | `Cancel the watches` | this skill |
| 4 | `Print the banner` | this skill |

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

1 — Write the handoff
---------------------

Before anything stops, so the record survives the stop. **Template fill
only**: the handoff is written from the record and the harness's issue and
pull-request state, never from what an implementor could be asked — no
implementor is messaged for a summary, because the answer is a wait and
this skill has none.

**One handoff comment per task issue at sea**, in this shape:

```markdown
## Handoff — fleet stood down <UTC timestamp>

Implementor `<id>` (<session|subagent>) was retired by stand-down. The work
is yours to reclaim.

- Branch: `<branch>` — <link>. The origin tip is authoritative as of this
  comment.
- Pull request: <#N and state, or "none open">.
- Worktree (this machine): <path, or "none">.

Unpushed work in a retired session's cloud workspace dies at the archive —
check the branch before assuming anything was lost. A local worktree
survives the retirement and carries whatever was never pushed.
```

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

2 — Stop the fleet
------------------

Everything in one parallel batch, and nothing polled.

**A web session is interrupted and then archived** — the stop follows the
turn, and the archive follows the stop. If the archive call rejects a
session it believes is still running, one retry after the interruption
completes; a second refusal is reported as a residual, not retried in a
loop. **The accepted loss is stated, never softened**: a cloud session's
workspace dies at the archive, and whatever it never pushed is gone. The
handoff on the task issue says so before the loss happens.

**A harness-local subagent is cancelled by its dispatch handle.** The
cancellation is immediate and unconfirmed — that is what makes it fast. The
subagent's worktree and anything it pushed survive it, which is why the
handoff names both the branch and the worktree path.

No wrap-up window is awaited anywhere. An implementor is not told to push
and given time to; it is stopped, and the handoff carries the state the
record already has.

3 — Cancel the watches
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

4 — Print the banner
--------------------

After the stops and the cancels have **returned** — not after they are
confirmed. The banner is the answer to the invocation, and it is printed
even where nothing was at sea, where the handoff failed to post, or where
residuals remain:

```
==================================================================
 STAND-DOWN COMPLETE — SAFE TO STOP
 Stopped: 5 implementors (3 archived, 2 cancelled) · record: <epic URL>
 Residuals: none
 Resume: /embark
==================================================================
```

Residuals are listed, one line each, never silent: an implementor that
could not be stopped, a comment that failed to post, a watch that could
not be cancelled. **A handoff that failed to post never blocks the stops**
— a lost record is better than a fleet left running — and the banner says
the record gap by name. The session ends after the banner: nothing is
re-armed, and the next turn on this work is a resumed `embark`.


Where it stops and waits
========================

Nowhere, by design. The invocation is a stop instruction, and every stop
below it runs through: no permission is asked to comment, to archive, to
cancel, or to print the banner. The two things that look like stops are
reports instead:

- **Nothing is at sea** — at `Read the fleet`. The banner prints with a
  zero count and the reason; if the invocation named an issue that is not
  an embarked epic, the report says which skill takes it — `undertake` for
  a task issue, `embark` for an epic still to work.
- **A residual** — at `Print the banner`. Named in the banner, one line
  each, and left for the person reading it. Nothing here retries a
  residual twice.

The one wait this skill never takes is the one `embark`'s own ends take:
`Close the epic` is `embark`'s, and a stand-down is not asked for when the
last wave comes in.


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
- **Does not message the fleet.** A correction or a wrap-up request is a
  wait for an answer, and the handoff is written from the record instead.
- **Does not fire on a worked-out epic.** `Close the epic` ends an embark that
  succeeded; this skill ends one that was interrupted.
- **Does not fire on a single issue.** One `undertake` has no fleet; the
  session holding it can simply stop, and its claim comment is already the
  record.
