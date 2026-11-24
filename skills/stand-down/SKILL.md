---
name: stand-down
description: >-
  Use for `/stand-down` when an embarked epic's work must stop: a fleet is
  stood down, the machine is put away, or an embark ends short of the last wave
  landing. Supplies cancellation of the orchestrator's watches first, the
  wrap-up that commits and pushes every implementor's work, one handoff per
  task issue, the epic stand-down comment, and the stop and archive. Not for an
  epic worked out (`embark` reports it) or a single issue (`undertake`'s stop).
---

# Stand-down

An embark in progress, a stopped fleet out, and a handoff that lets the next
session pick the work up. `embark` dispatches a fleet per epic and watches it
through GitHub; this skill is what ends that watch when the user must stop —
the laptop going to sleep is the common case — before the last wave has come
in.

This skill owns watch cancellation, securing work, handoffs, fleet retirement,
and the banner; `embark`, `epic`, `issue-deps`, and `provenance` own their
respective dispatch, state, graph, and attribution contracts.

**Speed is the design constraint, amended by one wait.** The user asked to
stop, not to orchestrate a stop. The steps below run in parallel batches,
never poll for confirmation, and allow one bounded retry anywhere. The one
exception is `Secure the work`'s wrap-up wait, bounded by a single shared
deadline for the whole fleet — the only wait this skill takes, and never an
answer awaited from an implementor: messaging here is one way, and what the
wait watches for is a turn ending, not a reply. Anything slower than that is
a residual the banner reports, never a further wait.

**Stopping starts at the invocation.** From the moment this skill fires, this
session does none of `embark`'s work: no landing, no recovery, no nudge, no
answer to an implementor's report, no review, and no CI fix. A wake that
arrives during the stand-down or after the banner is dropped with a one-line
note. That covers a backstop, a pull-request event, a CI result on a
work-in-progress push, a child-session event, and an implementor's report.
Harness guidance to drive a watched pull request green does not restart the
watch: the user asked to stop, and the harness itself says to stop following
up when the user asks.

**Load only what the stop needs.** That is this file, the reference for the
harness in use, and `provenance` for the block each write carries. `embark`,
`epic` and `issue-deps` own what this skill reads, but they are not loaded to
stand down: the muster rolls and claims are read as written, and the
reference names every call.

**The routes are per harness, and they live beside this file.** Every call
the steps below need is named in words here and resolved to a route there:
[`references/claude.md`](references/claude.md) for Claude Code,
[`references/omp.md`](references/omp.md) for Oh My Pi, and
[`references/codex.md`](references/codex.md) for Codex. Read the one for the
harness in use before `Read the fleet`. Where a surface has no primitive a
step needs, its file says so in words — silence would read as oversight.

**Cite steps by their stable names**, not their sequence numbers.


The sequence
============

| # | Step | Owner |
| - | ---- | ----- |
| 0 | `Read the fleet` | this skill, `embark` |
| 1 | `Cancel the watches` | this skill |
| 2 | `Secure the work` | this skill |
| 3 | `Write the handoff` | this skill |
| 4 | `Stop the fleet` | this skill |
| 5 | `Print the banner` | this skill |

0 — Read the fleet
------------------

Read the epic's ownership transitions and latest landing preference, and each
named task's current claim and handoffs. Consult the harness lifecycle and
dispatch handles where available. A historical claim alone is not liveness.
A confirmed finished or failed worker is retired; an unknown lifecycle is not
proof of retirement. Treat an unconfirmed live worker as a residual, and do
not authorize a concurrent writer. Cold recovery uses the durable mapping and
task records, not lost dispatch handles.

The reads run in one parallel batch.

**No epic, or an epic with nothing at sea, is not an error.** `Cancel the
watches` still runs, because a backstop or a subscription can outlive the
last implementor. Then `Print the banner` runs, with the count of what was stood down at zero and
the reason named — the invocation is a stop instruction, and the answer to
it is the stop.

1 — Cancel the watches
----------------------

First, so nothing wakes this session back into `embark`'s work while the
stand-down runs. The CI that `Secure the work`'s pushes start is the common
case: left subscribed, each result would arrive as a pull-request event
during the wrap-up wait. Fire-and-forget, by the identifiers the record holds,
in one parallel batch, sent with `Secure the work`'s interrupts: the backstop
timer behind the wake slot, any persistent watcher a CI wait left running,
and every pull-request subscription the watch subscribed. Record failed
cancellations and live watches as residuals, not successful transient timer
identifiers.

A cancel that fails is a residual for the banner, not a wait. The
orchestrator's own session ends at the banner regardless: no wake is
re-armed, and no check-in restarted.

2 — Secure the work
-------------------

Before the handoff is written, so its branch line describes what actually
reached origin rather than what an implementor merely held. Runs in one
parallel batch across the fleet — one wrap-up per web session, one
cancel-then-commit per harness-local subagent — and nothing here waits on
more than the one deadline below.

**Web sessions (Claude Code).** Interrupt the session, then address it the
way `embark`'s `Recover a session` addresses a correction — the address the
muster roll records — with the wrap-up: cancel its own wake timer and
pull-request subscriptions, commit everything in progress and push it, then
end the turn without starting anything else. `undertake`'s `The wrap-up` is
what the session obeys, and the reference file names what the message must
say so that a session that does not reread that section still stops.
Normally the task branch is both local and remote. For the primary-held designation mapping,
commit on the local execution branch and push to the recorded remote push
branch with its configured non-force upstream/refspec. Never push or open a
PR for the local-only name.
Then wait on one shared deadline until every session's turn has ended or the
deadline passes; the reference file names the send, the read and the deadline.
Leaving that wait is not itself securing: a session the deadline outlasts and
a session whose turn ends in error before its push completes are archived
anyway at `Stop the fleet` and reported as a residual in the banner, by name —
securing its work was attempted, not guaranteed.

**A session whose send fails while it is still live is interrupted and never
archived.** It cannot be told to push, and an archive destroys whatever it
holds unpushed. Where the send errors and the session read says it is still
live, it is interrupted alone. It is a residual in the banner and in its task
issue's handoff, with its session link, so that a person can push or archive
it later. A session whose send errors and whose read reports it archived,
failed or not found is not live and is archived at `Stop the fleet`.

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
unfinished work from a stand-down. It stages named files — `provenance`'s
rule against `git add -A` and `git add .` holds here too — and it skips no
hook and no test. It opens no pull request and marks nothing ready. A branch
with nothing to commit is pushed as is, so origin carries whatever was
already committed even where this step adds nothing new.

**A worktree, or a session, that cannot be committed or pushed is a
residual.** Named in the banner, the same as any other; nothing here retries
past the one bounded attempt.

3 — Write the handoff
---------------------

After the work is secured, so the record describes the pushed tip rather
than a tip about to move. Write one concise recovery record on each task
issue, using observed facts; do not ask an implementor to summarize. Include
the branch and worktree, observed remote head, any unsecured work or failed
push, and pull-request state when relevant. Say that no unsecured work remains
only when observed. Add worker lifecycle only when it affects recovery, along
with applicable authorization or stop limits and a concrete next action. Omit
inapplicable facts; state an uncertainty only when it affects safe recovery.
Never infer the remote head from the local tip.
An agent-written summary does not grant permission, and an unavailable
private source is not verified authority.

The active route adds `provenance` to each comment. Omp's wrapper appends its
block after the authored body, including the envoi; both blocks name this
stand-down session rather than any retired implementor's.

Carry authorization and stop information already available in the handoff.
`undertake` owns their meaning and revalidation. An agent-written summary
does not grant permission, and an unavailable private source is not verified
authority. Do not delay stand-down to reconstruct missing records or request
approval.

**One stand-down comment on the epic** records the landing preference, links
to the task handoffs, and exceptional residuals such as a failed push, failed
stop, unresolved worker lifecycle, or live watch. Do not repeat the task
handoffs, worker lifecycle already recorded there, or successful transient
timer IDs. Add a residual only when observed, and omit that line when none
remain. Do not claim a worker retired when its stop was not confirmed.

```markdown
## Stand-down — <UTC timestamp>

Landing: <orchestrator|by hand>

Task handoffs:
- #144 — <handoff link>

Resume: an explicit `/embark <epic>` reads these records and checks lifecycle
and current claims before dispatch; a later wake alone does not resume work.
```

An explicit resumption is not automatic replacement after cancellation. It
does not waive original authority, stop limits or exhausted recovery bounds.
Resolve unsecured local-only work before dispatching another writer.

**The stand-down comment ends with an envoi in its authored body**: a brief
farewell stanza for the watch, each line italicised as
[`HAIKU.md`](../../HAIKU.md) shows. It is last so the task handoffs and resume
line are found first. Omp's wrapper appends provenance after the envoi; other
routes place the block before it. Task handoffs carry no verse: each hands
work to whoever reclaims it, and verse never attaches to a write somebody has
to act on.

The landing mode is copied unchanged from the latest record into this
superseding comment. A resumed `embark` therefore reads the same opt-out or
default after every earlier muster roll has been superseded.

The epic's body is **not** edited. The stand-down comment records retired
ownership; resume reads the durable comments and implementor lifecycle, then
derives eligibility from the current graph and scheduling constraints.
No body wave-status update is required.

**Idempotent re-entry.** A stand-down interrupted by a session death is
re-run, not duplicated, and the writes are idempotent one by one: a handoff
comment already on a task issue is not posted twice, and a stand-down
comment already on the epic is not posted again when its facts are unchanged.
A `## Handoff —` comment after the latest claim (or anywhere when there is no
claim) counts only if it captures the same observed pushed head, unsecured
local work, worker state and stop limits. Unknown or changed recovery facts
require a new handoff; the same remote head alone is not enough. Write only
what is missing.

4 — Stop the fleet
------------------

Everything in one parallel batch, and nothing polled beyond `Secure the
work`'s one bounded wait, already spent by the time this step runs.

**A web session is archived, unless its send failed while it was live.** It was already
interrupted and sent its wrap-up at `Secure the work`; this step is the
archive alone. It runs whether that session's turn ended inside the deadline
or not — a session the deadline outlasted was already named a residual there,
and archiving it here does not undo that naming. **A live session whose send failed is
not archived**: it was interrupted only, and stays a residual with its link. If the archive call rejects a session it believes
is still running, one retry after the interruption's result is in; a second
refusal is reported as a residual, not retried in a loop.

**A harness-local subagent needs no second stop:** `Secure the work` already
attempted cancellation and securing before the handoff.

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
could not be secured — the wrap-up deadline passed, its send failed while it was live
(left unarchived, named with its session link),
its turn ended in error before the push completed, or a worktree would not
commit or push — an implementor that could not be stopped, a comment that
failed to post, or a watch that could not be
cancelled. **A handoff that failed to post never blocks the stops**
— a lost record is better than a fleet left running — and the banner says
the record gap by name. The session ends after the banner: nothing is
re-armed, and the next turn on this work is a resumed `embark`.


Where it stops and waits
========================

No additional wait: `Secure the work` owns the bounded wrap-up wait.
Nothing at sea routes to `Read the fleet`; residuals route to
`Print the banner`. A single undertaking stops through `undertake`'s
`The stop`; a completed epic closes through `embark`.


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
- **Does not fire on a single issue.** One `undertake` has no fleet. Its stop
  is `undertake`'s `The stop`, which secures the work and leaves the handoff
  a claim comment cannot.
