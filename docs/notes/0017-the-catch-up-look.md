# No durable wake, so every pickup takes the base-currency look

**Status:** decided, 2026-09-15.
**Provenance:** reported by the operator from live Omp sessions — an
`undertake` run's pull request sat behind its base and no session noticed.
The answer was chosen by an agent in the pull request that carries the change
it justifies.
**Resolves:** [#249](https://github.com/jmcvetta/daily-driver/issues/249).
**Amends:** [`0011`](0011-two-harnesses-one-skill-tree.md), which stopped
`Keep it current`'s cadence on Omp and left the catch-up unnamed.

## Report

`0011` measured the Omp boundary: `daily_driver_schedule` is cleared at
`session_shutdown`, and nothing on Omp wakes a session that has ended. The
consequence it recorded was that `Keep it current`'s cadence — which outlives
the turn that armed it — stops at `Ready for review`. What `SKILL.md` put in
its place was a promise: *the branch is kept current by the next session that
picks the pull request up*. Nothing defined what picking the pull request up
means, no skill named a read the picking-up session takes, and so no session
ever took one. A branch went behind its base and stayed there; the promise
was the failure.

The same hole sits in `review-cycle`'s Omp route. A resumed owner reconnects
to Hub, consumes the replayed completion of its CI watcher, and reads the
checks — and never asks whether the base moved while the session was away. A
green run on a head the base has since moved past answers the check question
and not the currency question.

## Decided

**The catch-up look is the first read of every turn that lands back on the
pull request.** On a surface without a durable wake, the turns the session
already has are the only check-ins it will ever get: a resume, a Hub
reconnect that replays a pending completion, a user turn that touches the
pull request. Each such turn reads the pull request's base currency before a
CI read, a thread read, or whatever the turn was otherwise going to do. On
Omp the read is `gh pr view <number> --json mergeStateStatus,mergeable`;
`BEHIND` runs the update-branch merge and the turn continues, `DIRTY` is the
conflict stop, and every other state needs nothing. The reference files name
the call; `SKILL.md` names the rule in words, because the rule is
harness-neutral — Codex has no durable wake either, and its reference gains
the same look.

**The currency read comes before the check reads, in the resumed turn too.**
This is the ordering [`0010-ready-wants-a-current-base.md`][0010b] applied at
the gate — test currency first, because a merge moves the head and a check
answer about the old head is an answer about a commit nobody will read —
applied to the pickup. The replayed completion is a check answer, not a
currency answer; the two reads are taken in that order and neither stands in
for the other.

**The look costs one call and merges nothing on its own.** A `CLEAN` answer
cost one call and ends the look. This is what makes every-turn affordable,
and it is why the look is not the cadence: the cadence *merged* on its
schedule, the look only *notices*, and the merge still belongs to
`Keep it current`'s update-branch call.

## Rejected

**A polling loop or a second watcher process for the base branch.** It is
the durability Omp does not have, asked for again. A process can preserve a
watch and replay a completion; it cannot perform the agent turn that merges,
and [`0011`](0011-two-harnesses-one-skill-tree.md) already drew that line.

**Arming `daily_driver_schedule` as the catch-up.** The timer dies at
`session_shutdown` by measurement, and the failure this note answers is
precisely a turn that never comes. The timer stays what it was: a check-in
for a session that is alive, not a watch for one that is gone.

**A subscription for base-branch pushes.** [`0007`][0007] already rejected
the subscription for this step: it carries comments, reviews and checks, and
never a push to the base branch. Nothing about the Omp case changes that.

**Leaving the promise as written.** *"Kept current by the next session that
picks the pull request up"* named a session that had no instruction to look.
A catch-up nobody is told to run is the cadence stopped twice — once by the
boundary, once by silence — and the second stop is the one this note removes.

[0007]: 0007-keeping-the-branch-current.md
[0010b]: 0010-ready-wants-a-current-base.md
