# Repo-local review rules live in the repository's own `CLAUDE.md`

**Status:** decided, 2026-09-07.
**Provenance:** chosen by an agent in
[#55](https://github.com/jmcvetta/daily-driver/pull/55) — the same pull request as
the change it justifies — and ratified by that merge, not by a separate call
from the author.
**Resolves:** [#53](https://github.com/jmcvetta/daily-driver/issues/53).

Two review rules shipped in the global layer that describe two of the author's
Terraform repositories and nothing else: never flag `yor_*` / `git_*` tags in
Terraform resources as stale, and require a reason on every `checkov:skip`.
Both are correct, and both are genuinely unlearnable — a general-purpose
reviewer cannot infer either, which is why
[#35](https://github.com/jmcvetta/daily-driver/issues/35) puts them out
of scope for its measurement rather than expecting a built-in to reproduce
them.

Correctness was never the question. Placement was. The plugin loads on every
surface and in every repository; these two rules are meaningful in perhaps two
of them, and everywhere else they are context spent on Terraform conventions
for a repository with no Terraform. That is subsidiarity read backwards: a rule
belonging to one repository had come to sit in the layer that reaches all of
them.

## Decided

**The rules move to project memory** — `CLAUDE.md` in the repositories they
actually describe. They are removed here:

- `agents/security-reviewer.md` carried the Yor rule inline, so it shipped on
  every surface whether or not `review` ever returns from the attic. This is
  the live half of the change.
- `attic/skills/review/references/review-guidelines.md` carried both. Nothing
  under `attic/` is loaded, so this costs no context today — but the attic
  exists so that a `git mv` brings a skill back, and a rule left there is a
  rule that comes back with it.

**The plugin carries no mechanism for repo-local review rules.** `CLAUDE.md`
is already read on every surface, is already the level subsidiarity names, and
already reaches a reviewer subagent — that last is measured, not assumed:
R2's table in
[`plugin-replaces-global-memory.md`](../planning/plugin-replaces-global-memory.md)
settles `CLAUDE.md` → subagent as **yes**, which is the row the constitution's
own `PreToolUse` hook exists to match. A conventional path of our own — some
`.claude/review-rules.md` a reviewer is told to look for — would be a second
memory layer with the same job as the first, and the reviewer would have to be
told about it in the global layer, spending in every session exactly what this
decision set out to stop spending. YAGNI settles it, and the `judgement-call`
gate is why it is settled here rather than asked.

Nothing enforces the boundary but the author, in the same way nothing enforces
the GoDoc rule. The tempting guard is a blocklist of Terraform vocabulary in
CI, and it is declined: it would fail the day a legitimate mention landed, and
it teaches a future reader the wrong rule — the test is not *which words*, it
is *how many repositories does this describe*.

## What this does to #35's measurement

Two of the six arms [`0001`](0001-built-in-review-surface.md) defines are
configurations *of this file*: **D**, one general-purpose agent carrying
`review-guidelines.md`, and **E**, `/code-review medium` plus
`review-guidelines.md` and no judgment panel. Both now carry a guidelines file
with no repo-specific rules in it.

That matters because `0001` names the inference it was guarding against: a
small B − A read as "a thin wrapper would do", "one that silently assumes the
repo-specific rules survive the move". After this decision they do not survive
the move — they are not in the file to move — so arms D and E measure the
built-in plus a *general* checklist, and neither can be read as evidence about
repo-specific rules either way. `0001` carries an `Amended in part` header
saying so.

## Where the rules go now

Removal is not deletion; the rules are needed where they apply, and a decision
record is not where anyone bootstrapping a repository will look for them. The
block to paste is in
[`bootstrapping-a-repository.md`](../bootstrapping-a-repository.md) under
*Repo-local review rules* — one copy, so the two cannot drift.

## What would change this

A third repository needing the same rules is not enough — it is a third paste.
What would reopen it is repo-local review rules that cannot be written as prose
in `CLAUDE.md`: rules a reviewer must *execute* rather than read, or a set large
enough that loading it unconditionally is the cost `CLAUDE.md` avoids. Neither
exists today.
