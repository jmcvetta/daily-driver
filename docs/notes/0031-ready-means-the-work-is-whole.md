# Ready means the work is whole

**Status:** decided, 2026-10-06.
**Amends:** `undertake`'s `The gate` and `A round after ready goes back to
draft`. Supersedes neither; `0021` keeps its subject.

**Observed.** #558 was the pull request for #555. Every gate read held on its
head `cb7d8f0`: base merged, CI green, every thread resolved, the verification
pass clear, the completion notice posted at 16:29:18 UTC. The session marked it
ready at 16:29 UTC and it was merged at 16:31:10 UTC. The head carried no
fixture for #555's acceptance item "unavailable model routing does not prevent
other eligible tasks from launching". #567 and draft #568 carry it now.

## Why it could happen

**The gate read GitHub and not the issue.** Six reads, all facts GitHub holds
about the head. None compared the head with the issue's acceptance section,
looked for uncommitted or unpushed work, or asked whether more change was
planned. A partial head passed them all, and the rule to mark ready in the same
turn then fired on it.

**The return to draft was bound to the round.** The push that changes content
comes before the round, so a ready pull request carried unreviewed content until
the round began. A person merging from the GitHub UI reads no completion notice.

## Decided

**A completeness read comes first.** The head carries the whole of the issue's
work: a clean worktree, nothing unpushed, every acceptance item mapped to a diff
file or answered with a reason, and no further change planned. Where it does not
hold, the sequence returns to `Implement`. It is not a stop and not a question,
so `Where it stops and waits` is unchanged. It is first because every later read
is about the head a person will merge.

**The draft comes before the content push.** The pull request returns to draft
before any push that changes its content. The base merge is the exception: it
changes no content and earns no round (`0022`).

## Where it landed

`skills/undertake/SKILL.md` (`The gate`, `A round after ready goes back to
draft`), the three `skills/undertake/references/{claude,omp,codex}.md` route
tables, and eval rows 18 (two new) with rows 10 and 13 updated to state the new
condition as met.
