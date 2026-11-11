# One wake slot, and a turn never ends with it empty

**Status:** decided, 2026-09-09.
**Provenance:** reported by the operator from a live session — near the end of
an `undertake` run the session wrote *"Projection re-rendered on 392598e …
No action. Waiting on CI."*, and then slept. CI went green minutes later and
nothing woke the session. The answer was chosen by an agent in
[#138](https://github.com/jmcvetta/daily-driver/pull/138), the pull
request that carries the change it justifies.
**Resolves:** [#137](https://github.com/jmcvetta/daily-driver/issues/137).
**Amends:** [`0006`](0006-waiting-for-ci.md) and
[`0007`](0007-keeping-the-branch-current.md), which each specify a
`send_later` timer without knowing about the other's.

Two rules already said *one timer*. `review-cycle`'s `The backstop` said
"exactly one timer, ever", armed only on the wake that timer itself caused.
`undertake`'s `When it looks` said one `send_later` at a time for the
`Keep it current` cadence. Both are correct on their own, and together they
lose the session.

The two overlap at `After the merge`: the cadence timer is in flight for the
whole life of the pull request, and the base merge then enters `How to wait`,
which arms a backstop. `End the wait` cancels the backstop and unsubscribes.
So the wait's last act is to empty the one slot, and the rule that would refill
it — *arm a replacement on the wake the previous timer caused* — never fires,
because no timer fired. There is no wake, no subscription, and nothing left to
notice that CI is green.

The same hole opens without a merge. Any wake that is not the cadence timer's
own — an event wake, a comment, a user turn — ends a turn under a rule that
only re-arms on the timer's own wake. The report above is that case: a
check-in wake that found a run in flight, did nothing by design, and had
nothing to hand the next wake to.

## Decided

**The session holds one wake slot, and never ends a turn with it empty while
the pull request is open.** The slot is one `send_later`, identified by the
`trigger_id` it returned. It empties two ways — the timer fires, or a wait
cancels it — and both are the same instruction: fill it before the turn ends.

This replaces *arm a replacement on the wake the previous timer caused*. That
rule was written to stop a timer being armed per event, and the emptiness test
does that job without the hole: a wake with a timer still in flight arms
nothing, whatever woke it.

**Ending a wait hands the slot back.** `End the wait` cancels the timer in the
slot — its own backstop, or the caller's cadence timer it borrowed rather than
arming a second — because an armed `send_later` fires into the middle of
`/code-review`. Where the caller keeps a cadence, the caller arms it again
before that turn ends, after the round rather than into it. Where there is no
such caller, nothing is armed: check-ins belong to a sequence that ends them.
The wait owns the reading loop; it does not own the caller's watch.

**Rejected: two slots, one per purpose.** It removes the hand-back, and buys a
second timer that fires while the first is doing the same read — which is the
duplication `The backstop` already refused. One slot with a stated owner at
each moment is cheaper to reason about than two that must be told apart on
every wake.

**Rejected: leaving it to the subscription.** The subscription is dropped with
the wait, and `0006` already records that its delivery is not a guarantee. A
wait that ends by dropping both mechanisms is the failure this note is about.
