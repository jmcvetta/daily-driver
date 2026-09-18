# The gate is a read — and a pushed fix always earns its pass

**Status:** decided, 2026-09-18.
**Amends:** `undertake`'s `The gate` and `review-cycle`'s `Verify the fix
delta`. Supersedes neither; both rules keep their subject and change their
shape.

**Observed.** Two stalls, in sessions running the undertaking to its end.

The first: a pull request current with its base, green on the merged head,
with every thread resolved and the review round recorded clean, stayed a
draft while the session asked the user whether it was ready to mark ready.
The user's answer was that they did not know — it was the agent's work, and
the agent held every fact the question was about.

The second: a scope whose first `Verify the fix delta` pass found defects,
and whose second pass found more. Both batches were fixed and pushed. The
cap then refused a third pass, so the pull request sat in draft carrying a
fix nothing had read, and only a person could move it.

## Why it could happen

**The gate was written as six conditions and no procedure.** Every one of
them is answerable by a call — GitHub's merge state answers two, the thread
reads answer two more — but the section named none of those calls. It listed
what must be true and left the session to decide whether it was. A condition
you weigh is a condition you can take to somebody else, and *is this ready?*
is a natural thing to hand upward. The text also named only one failure: a
red pull request marked ready. The opposite failure, a finished pull request
left in draft, had no name, and an unnamed failure is the safe-looking one.

**The cap counted passes, not what it feared.** Two passes per scope was
written against review ping-pong — a session buying itself another round by
calling a commit a fix. But a pass is also the only thing that reads a
pushed correction. Spending the budget on defects that were then fixed left
the last fix unverified, which is the state the whole round exists to
prevent, reached by obeying the rule that was meant to prevent it.

## Decided

**The gate is a read, not a judgement.** Six conditions, four reads, each
one a call the harness reference names, and the last read followed in the
same turn by the call that marks the pull request ready. Nothing comes
between them: no summary first, no permission asked. The user is named as
never a gate condition — no stop under `Where it stops and waits` is a
confirmation of readiness, and the person who did not do the work cannot
answer for it. A draft that satisfies every condition is named as the false
claim it is: the same lie as a red pull request marked ready, pointing the
other way.

**A pushed fix always earns the pass that confirms it.** The loop ends on
the first clean pass. Three consecutive passes that each record defects is
the wall — the constitution's *When you hit a wall*, reached honestly —
and it is reported with the defects on the pull request rather than hit in
silence. Commits, resumes, rewrites, bot findings and CI fixes are still not
passes and still move nothing; only a pass that records defects moves the
count.

## Where it landed

`skills/undertake/SKILL.md` (`Ready is a gate, not a step`, rewritten; the
duplicated sentence at `Ready for review`; the no-permission line under
`Where it stops and waits`; and the second step numbered 10, which is
`Keep it current` and is 11 in the table), the three
`skills/undertake/references/{claude,omp,codex}.md` route tables, which now
carry the gate's own reads, `skills/review-cycle/SKILL.md` (`Verify the fix
delta` and `Where it stops and waits`), the three
`skills/review-cycle/references/{claude,omp,codex}.md` record blocks, whose
`pass: <1|2>` and `cap:` fields became `pass: <n>` and `wall:`, and two eval
rows. No step was renamed.
