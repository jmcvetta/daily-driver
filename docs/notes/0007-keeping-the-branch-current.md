# The branch is kept current by a base merge, and the merge does not buy a review

**Status:** decided, 2026-09-08; amended, 2026-09-08 and 2026-09-09.
**Provenance:** chosen by an agent in
[#115](https://github.com/jmcvetta/daily-driver/pull/115), the pull
request that carries the change it justifies, and ratified by that merge. The
cadence was amended straight after that merge, by the author's correction that
`master` here moves every few minutes.
**Resolves:** [#113](https://github.com/jmcvetta/daily-driver/issues/113).

`undertake` ended at `Ready for review`. Commits land on `master` several times
a day here, so a pull request waiting on a human reviewer goes behind its base
within hours, and nothing in the sequence noticed. The branch a reviewer reads
is then one CI tested against a tree nobody will merge into.

The step that fixes this is `Keep it current`, and writing it needed three
answers.

## Decided

**The merge is `mcp__github__update_pull_request_branch`, not a local
`git merge`.** The step runs long after `Implement`, on a session that may be
on another branch, in a container that may have been rebuilt — a step that
needs a checkout is a step that fails first on the surface it matters most on.
The call also answers the question it is asked: GitHub reports the branch as
already up to date when there is nothing to bring in, so nothing has to
measure how far behind the branch is. A conflict is where it stops helping —
it fails and changes nothing — and a resolution is a local merge from there.

**Rejected: a rebase.** It rewrites history a reviewer is reading, and it
voids the head SHA `review-cycle` records at `Review the head`, which is the
mark its whole re-review test is measured from. A merge commit costs a line of
history and keeps both.

**A clean base merge does not earn a review round.** `/code-review` reads the
pull request's three-dot diff. A clean merge leaves that diff byte-identical to
what `Review the head` already reviewed, so a second round reads the same bytes
and reports the same nothing — daily, on a base branch that moves daily. This
is not a new rule: `review-cycle`'s `Does it go again?` already files a clean
base merge under `Neither`. What was missing was the step that performs the
merge, and the statement of when the exception bites.

**Rejected: reviewing the merged base changes.** It is the intuitive answer to
*"the base changed something my branch depends on"*, and it is the wrong
instrument. That breakage is semantic, it does not appear in the branch's own
diff, and what finds it is the build: CI runs again on the merged head, and a
red check is answered under `Fix, answer, resolve, push`. A review panel
reading a diff that did not change would not have found it.

**The exception is a conflict resolution.** Resolving a conflict rewrites the
branch's own files, which `Does it go again?` already classifies as
`Changing what the code does`. One round over that, on the existing test,
with no second test written for it.

**A round after ready sends the pull request back to draft.** Ready is a claim
that the branch is finished; a branch being changed under a reviewer is not.
The return is through the existing gate — green CI, no unanswered thread,
every finding closed — rather than through a second gate written for the
second round.

**Amended by [`0010`](0010-the-wake-slot-is-never-empty.md),
2026-09-09:** the two timers this note and its sibling each specify are one
wake slot, and a turn never ends with it empty.

**The step looks on a check-in every two minutes, with one floor: a CI run
still in flight.** A base branch is not a pull request event — nothing wakes a
session when `master` moves — so `Keep it current` is scheduled rather than
woken. One `send_later` at a time, ended by the merge or the close of the pull
request. Two minutes is the interval `review-cycle` already waits on CI with,
and `master` here takes a commit every few minutes, so anything slower is a
branch held behind deliberately. The floor exists because a merge restarts the
run: a check-in that finds the last merge's run still going does nothing. On
this repository CI answers in seconds and the floor rarely bites.

**Rejected: a fifteen-minute check-in**, and an hourly one before it. Both were
written against a base branch that moves a few times a day. This one moves
every few minutes, so both leave the branch behind for most of its life, and
the merge they were rationing costs a call and a run measured in seconds.

**Rejected: a merge with no floor at all.** Merging while the last merge's run
is still going restarts that run, so on a slow CI the branch would never hold a
green check. The floor above is that case and nothing wider — it is not a
licence to ration the merge.

**Rejected: a pull request subscription.** `review-cycle` takes one for the CI
wait and drops it with the wait. Keeping it standing would not answer this
question — it carries comments, reviews and checks, and never a push to the
base branch — so it would be a subscription held for events that cannot
arrive.
