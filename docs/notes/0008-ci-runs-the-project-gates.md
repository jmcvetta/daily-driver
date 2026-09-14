# CI runs the project's gates, not this machine

**Status:** decided, 2026-09-08.
**Provenance:** put to the author while implementing
[#110](https://github.com/jmcvetta/daily-driver/issues/110), handed
back, and chosen by the agent in the same pull request as the change it
justifies.
**Resolves:** the contradiction [#110](https://github.com/jmcvetta/daily-driver/issues/110)
opens between its own rule and two rules already in force.

#110 asks for a prohibition: *do not run a project check locally; push and read
what CI reports*. Two things already said the opposite. The constitution's
*Before you call it done* said **"Run them, rather than reasoning about whether
they would pass"**, and `undertake` carried a `Run the gates` step whose stated
purpose was that the draft opens green. Writing #110's rule and leaving those
alone would put a prohibition and an order over the same action in the same
toolkit, which fires for neither.

## Decided

**The gates run on CI.** The constitution keeps the standard — it is not done
until the project's gates pass — and names CI as where that is found out. A
local run is for one thing: reproducing a specific failure you are about to
fix.

**`undertake` loses its `Run the gates` step.** The push at `Open the draft` is
what runs them. `Review the head` already waits for CI on the pushed head and
already treats a red check as a fact about the branch rather than a reason to
hold the review, so a draft that opens red is answered at `Fix, answer,
resolve, push` with no step to remove it earlier. Eleven steps now, not
twelve.

## What it costs

A change that a free offline `make check` would have caught now costs a CI
cycle instead. That is real, and it is the price of a bright line. The
alternative considered was keying the rule to cost — *do not run a check that
is slow, paid, or that the project says is CI's job* — which keeps the cheap
local run and leaves `undertake` untouched. It was rejected because "slow" is a
judgement made mid-task, and a rule that depends on a mid-task judgement is the
disposition #110 is against. The whole point of #110 is that the rule fires
without being weighed.

## What it does not decide

Whether this belongs in prose at all. #110 says plainly that it does not: a
`PreToolUse` hook sees the command before it runs, and anything that costs the
user money should be enforced rather than instructed. That hook is not written
here, and this note does not argue against it.
