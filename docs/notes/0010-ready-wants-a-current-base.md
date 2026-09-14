# The ready gate wants a current base, and `Keep it current` supplies it

**Status:** decided, 2026-09-09.
**Provenance:** chosen by an agent in the pull request that carries the change
it justifies.
**Resolves:** [#134](https://github.com/jmcvetta/daily-driver/issues/134).

[`0007`](0007-keeping-the-branch-current.md) wrote `Keep it current` for the
window after `Ready for review`: a pull request waiting on a human goes behind
its base within hours, and nothing noticed. It left the other window open. The
base branch also moves while the work is being written, so a pull request could
pass the gate and go out to a reviewer already behind, or already conflicting —
the state the step exists to prevent, at the one moment the step did not run.

## Decided

**The gate carries the condition; `Keep it current` carries the merge.** A
fourth condition joins the three at `Ready for review`: the branch is current
with its base and merges cleanly. Nothing about *how* is written into the gate —
`mcp__github__update_pull_request_branch`, the merge-not-rebase rule, and the
conflict stop all stay where `0007` put them, and the gate cites the step.

**Rejected: a new step before `Ready for review`.** It would be `Keep it
current` written a second time, and the second copy is the one that goes stale.
What changed is not the work but when it first runs, so the step gained a line
saying its first run is before the gate rather than after it.

**The currency condition is tested first, before green CI and the threads.**
A base merge moves the head. Testing CI first and merging afterwards answers
the CI question about a commit no reviewer will read, and the pull request
would go ready on a head whose checks have not reported. Merging first costs
one CI run that the merge would have cost anyway.

**A conflict found here is the stop `0007` already wrote**, arriving earlier.
`update_pull_request_branch` fails and changes nothing, the resolution is a
local merge, and where both sides changed the same logic the constitution's
rule against guessing at intent stops the sequence. No second stop was written,
and the count under `Where it stops and waits` is unchanged.

**The cadence did not change.** `When it looks` already scheduled its first
look at `Ready for review`; now that look is the gate's, and the two-minute
check-in starts from the ready pull request as before.
