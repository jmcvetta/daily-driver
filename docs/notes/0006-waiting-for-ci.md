# Waiting for CI is a loop of turns, never a sleep

**Status:** decided, 2026-09-08; amended, 2026-09-08 and 2026-09-09.
**Provenance:** chosen by an agent in
[#100](https://github.com/jmcvetta/daily-driver/pull/100) — the same
pull request as the change it justifies — and ratified by that merge.
**Resolves:** [#96](https://github.com/jmcvetta/daily-driver/issues/96).

`review-cycle` opened `Review the head` with *"Wait for CI to report on the
pushed head first"* and stopped there. The requirement had no mechanism —
neither here, nor in `undertake`, which delegates the same wait to it. Nothing
in the repository said how to wait.

So sessions improvised, and the improvisation was a backgrounded `sleep`: a job
named *"Wait ~3 minutes for CI"*. It never came back. CI finished, the job sat
until it timed out, and the round stalled before the review it was waiting to
run. That is #96, reported from a live session.

## Decided

**The wait is a loop of turns: read the checks, wake later, read again, capped.**
*Amended 2026-09-08 — the wake is now a pull request subscription, and the loop
is its backstop; the interval is unchanged. See* Amended *below.*
**Amended by [`0010`](0010-the-wake-slot-is-never-empty.md),
2026-09-09:** the two timers this note and its sibling each specify are one
wake slot, and a turn never ends with it empty.

`review-cycle`'s `How to wait` carries the calls, the two-minute interval and
the fifteen-minute cap. Both numbers are chosen rather than measured; a
measurement is what may move them.

The shape follows from who can read a check. GitHub is reached through the MCP,
and only the model can call an MCP tool — not a shell, and not a background
job. The read is therefore something only a turn can do, so the delay between
two reads has to be something that ends a turn and starts another. On the
Claude Code Remote surface that is `mcp__Claude_Code_Remote__send_later`, whose
delivery is scheduler-side and survives a container restart.

**Rejected: a `sleep`, foreground or backgrounded.** A sleep is a timer, and a
timer answers a different question than the one being asked — it expires while
the checks are still queued as readily as it expires long after they went
green. Backgrounded it also has the failure #96 reports, and a wait that
depends on a process nobody is watching is a wait that can be lost. On this
surface a foreground `sleep` is refused outright.

**Rejected: a shell wait — `Monitor`, a backgrounded `until` loop, or a
blocking `gh pr checks --watch`.** This is the harness's own advice for waiting
on a condition, and it is right where a human is watching the terminal. It is
not right for a wait nobody is attending, and the reason is not that a shell
cannot read GitHub — where `gh` is installed and authenticated, it can, which
is why `How to wait` prescribes exactly that on a laptop. It is that neither
shape survives the session: in the foreground the watch is bounded by the Bash
tool's timeout, and refused outright on a surface that blocks `sleep`; in the
background it is bounded by nothing and cannot wake the session, which is #96.

**Rejected, then reversed: `subscribe_pr_activity`.** See *Amended* below.

**A surface with no wake performs no wait.** Where `send_later` does not exist
and the surface has nothing to block on, `How to wait` reads the checks once
and stops with a line naming what has not reported. Stopping is honest and the
user can answer it. A wait that is only claimed cannot be.

## Amended, 2026-09-08

The first decision rejected `subscribe_pr_activity` — the tool that delivers CI
results as wake events, with no polling at all. The reason given was that a
fallback loop has to exist anyway (a PR Steward can already hold the
subscription, and the tool is absent on a laptop), and that a round carrying
both mechanisms would be two things to get right where one will do.

The second half of that is wrong, and the user said so: the one mechanism left
standing is a two-minute poll, and a poll is a bad wait. It answers minutes
after the event it is waiting for, and it spends a turn every time it answers
*not yet*.

**Amended: subscribe first, and keep the loop as a backstop.** The event is the
wake; the check read is still the answer. The two-minute interval does not
move. It is no longer the thing that notices, but it is still the thing that
bounds the worst case, and the worst case is a wait with no events in it at
all — stretching it would slow down the only runs that depend on it.

Both cases are real, and neither is a reason to skip the subscription:

1. **A steward already holds it.** The call succeeds and the events go
   elsewhere. Detectable — the tool result says so.
2. **The delivery is not a guarantee.** The `subscribe_pr_activity` tool
   description promises comments, CI failures and successful check-suite
   rollups. The harness's own pull request guidance, delivered alongside the
   `subscription.created` event on 2026-09-08, qualifies it: webhooks *"don't
   reliably deliver CI success, new pushes, or merge-conflict transitions"*.
   The two are not reachable from the same place, which is why this note
   quotes the second — a wait for green cannot be built on the green event
   alone, and the claim that it cannot is checkable rather than recalled.

So the round does carry two mechanisms, and that is the correct number rather
than one too many. They are not two ways of doing the same thing: the
subscription decides *when the session wakes*, the read decides *whether the
wait is over*, and the timer only guarantees that a wake happens at all. The
cap and the stop are unchanged.
