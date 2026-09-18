# The merge is mechanical, and the watch that runs it needs no session

**Status:** decided, 2026-09-18.
**Provenance:** reported by the operator from live sessions on both
harnesses — an `undertake` run's pull request fell behind its base on Omp
once the session went away, and the Claude Code cadence died silently more
than once. The answer was chosen by an agent in
[#312](https://github.com/jmcvetta/daily-driver/pull/312), the pull request
that carries the change it justifies.
**Resolves:** [#310](https://github.com/jmcvetta/daily-driver/issues/310).
**Amends:** [`0011`](0011-two-harnesses-one-skill-tree.md), which scoped
`0010`'s never-empty wake slot to Claude Code and left Omp's watch to
catch-up looks; and [`0017`](0017-the-catch-up-look.md), which rejected a
watcher process for the base branch.

`Keep it current`'s cadence had one actor everywhere: the session. On Omp the
actor lived only as long as the session — `daily_driver_schedule` is cleared
at `session_shutdown` — and note 0017's catch-up look fires only on turns
that land back on the pull request, of which a user who has walked away makes
none. On Claude Code the actor survived, but only behaviourally: every wake
turn had to remember to re-arm the slot and recall why it fired, and the wake
prompt itself carried no instruction, so a thin wake turn ended the watch
silently.

## Decided

**The step splits into the merge and the watch.** The merge — the
update-branch call, the floor, nothing else — is one server-side call whose
safety conditions are one read. It needs no judgment and no session. The
watch is whatever keeps that call running, and each harness names its own: a
detached hub process where processes survive, a self-contained scheduled wake
where only wakes do, the catch-up look where neither does.

**On Omp the watch is a detached hub process.** `hub start` runs
`scripts/pr-keep-current.sh <number>` with `detached: true`: every two
minutes it reads state, merge status, and the check rollup, skips the tick
while a run on the head is in flight, merges when behind, exits 0 on merged
or closed, and exits 3 on a conflict. `Keep it current`'s judgment — the
ready gate, a red check, the milestone, the conflict stop — stays with the
session, which meets it on the catch-up look every turn that lands back on
the pull request. Hub still does not launch or resume the agent; the point is
narrower and enough: the merge was never an agent turn.

**On Claude Code the wake carries its own instructions.** The prompt given to
`send_later` states the whole check-in — re-arm first, then the
base-currency read, then act on what it finds — so the one-slot rule of 0010
is enforced at the start of every wake instead of wherever the turn remembers
it.

**`0017`'s rejection is overturned on its reason.** It rejected "a polling
loop or a second watcher process" because a process "cannot perform the agent
turn that merges". The conflation is the defect: the merge is a call the
process can perform, and the turns it cannot perform are exactly the turns
the watch never needed. The catch-up look stands — it is how the session
learns what the loop did and meets the judgment parts — but it is no longer
the only thing keeping the branch current.

**The CI-wait borrow goes with the timer.** The loop's floor already refuses
to merge under a run in flight, so on Omp a CI wait and the watch coexist
without a slot to negotiate. On Claude Code the wait still borrows the wake
slot and gives it back at `End the wait`.

## Rejected

**Keeping the timer as the Omp cadence while the session lives.** That is the
arrangement 0017's catch-up look already patched, and the operator's report
is that it still fails: the failure is precisely the session that is not
alive, and the catch-up look does not run in one.

**A rebase-based watcher.** `0007` already rejected the rebase: it rewrites
history a reviewer is reading and voids the head SHA the round recorded. The
loop merges, and only server-side.

**A watcher that judges.** A process that could close threads, decide the
ready gate, or resolve conflicts would need the model. The loop stops at the
conflict and leaves the stop where the session will find it.
