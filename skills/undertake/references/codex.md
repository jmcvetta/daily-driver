# Codex routes — undertake

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Oh My Pi's in [`omp.md`](omp.md).

**Codex has no GitHub tool of its own** — no `mcp__github__*` server, and no
built-in `github` tool with an `issue://` or `pr://` cache behind it. There is
one client, `gh` in the shell.


The issue
=========

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the issue` | Search the open issues | `gh search issues` |
| `Open the issue` | Open one, labelled | `gh issue create --label task` |
| `Read the issue and its edges` | Read the body, the graph and the comments | `gh issue view <number> --json body,labels,comments,blockedBy,subIssues,parent` |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> --body-file <path>` |

`--body-file` rather than `-b`: the claim carries backticks and markdown
links, and a double-quoted shell argument substitutes the backticks before
`gh` sees them. `pr-body`'s [`codex.md`](../../pr-body/references/codex.md)
makes the same argument at length.

`comments` is in that field list because `SKILL.md` reads the comments as
content: a correction to the body, a constraint an earlier session found, a
decision taken in the thread. It serves `Claim the issue` as well — a claim
already on the issue is what says the sequence is being re-entered, or that
another session got there first — but that is the smaller of the two reasons.
A read without the field has neither.

The `--json` fields in the read row need `gh` at its stated floor.
`issue-deps` owns the edge reads and picks its own client — two clients here
rather than three — so read that skill's routes before believing an empty
answer. So does `issue-labels`, whose `references/codex.md` says why
`--add-label` needs no read-first and the Claude route does.

For a `task`, read the `Model class` section and assess the current session
against [`issue-body`'s guidance](../../issue-body/references/model-classes.md)
before its claim or repository change. A suitable stronger session implements
directly. An unsuitable or unassessable session reports the mismatch; it does
not delegate merely to change cost.


The implementor
===============

No route, and that is the rule rather than a gap. `SKILL.md`'s `Implement`
owns it: the session running the sequence writes the code itself, so
`multi_agent_v1` carries no delegation here. That namespace belongs to
`embark`, which uses it to run several task issues at once. The one dispatch
inside this sequence is `review-cycle`'s briefed subagent at `Verify the fix
delta`, named in that skill's own reference file.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/codex.md` owns them |
| `The gate` | Read the review record | `gh pr view <number> --json comments` — the round's own `Review` and `Review verification` comments |
| `The gate` | Read the human-action notice | `gh pr view <number> --json body`, where `pr-body`'s notice sits |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Merge the base branch in | `gh pr update-branch <number>` |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |
| `The milestone` | Read the readiness state | `gh pr view <number> --json isDraft,mergeable,mergeStateStatus,headRefOid` |
| `The milestone` | Read the existing comments | `gh pr view <number> --json comments` |
| `The milestone` | Post the report | `gh pr comment <number> --body-file <path>` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/codex.md` names the full-review surface and
the briefed-subagent route `Verify the fix delta` runs on; a pass that dispatch
genuinely fails is what keeps the pull request draft.


The session
===========

**Codex exposes no session id, so the claim records `session: n/a`** — the
marker `SKILL.md` prescribes, not a diagnostic about the missing surface. The
`Model:` line repeats what the harness states is serving the turn — the
session's configured model — rather than a recalled name.

The branch comes from the task worktree's Git state:
`git branch --show-current` runs in that worktree. `OWNER/REPO` for the branch
link comes from the remote `task-worktree` resolved, never from an assumed
`origin`.


The milestone
=============

`SKILL.md` owns what the report says and when it is owed; these are the calls
that read the readiness state, find the claim's timestamp, and post it. They
are `gh` throughout, as everywhere on this harness.

**The readiness state is one read:**

    gh pr view <number> --json isDraft,mergeable,mergeStateStatus,headRefOid

`isDraft` false and `mergeable` `MERGEABLE` are two of the answers the report
needs, and neither is sufficient alone. `mergeStateStatus` answers the rest,
and here — after the draft is cleared — `CLEAN` is the only yes: `BEHIND` is
a base the branch does not carry, `UNSTABLE` a check that is no longer green,
`DIRTY` a conflict, and `UNKNOWN` and `BLOCKED` are states `SKILL.md` rules
out as readiness outright. Each is a wait, not a milestone. **`The gate` reads
the same field for less**, because a draft reports `DRAFT` or `BLOCKED` there
whatever its branch and checks are doing: only `BEHIND`, `DIRTY` and `UNKNOWN`
are that read's, and CI at the gate comes from `statusCheckRollup` instead.
`headRefOid` is the SHA the report binds to.

**The start is the claim comment's `createdAt`.** `gh issue view <issue>
--json comments` is the read `Read the issue and its edges` already makes —
`comments` is in its field list — and the claim is the comment carrying the
branch link and the `Model:` line. Take its `createdAt`; where more than one
comment carries that shape, the earliest of them is the start — a later
claim does not restart the clock. A resumed session finds the start with the
read it makes anyway. An issue with no recoverable
claim leaves the timing `n/a`, per `SKILL.md`.

**The report posts as a pull-request comment** — a pull request's comments
are issue comments:

    gh pr comment <number> --body-file <path>

`--body-file` for the reason `Claim the issue`'s row gives: backticks and a
markdown link in the body, and a double-quoted shell argument substitutes
them before `gh` sees them.

**Read the existing comments before posting** — `gh pr view <number> --json
comments` again, the report found by its opening line, `First-readiness
report`, the marker `SKILL.md` fixes; a resumed sequence that finds it posts
nothing.

**The provenance** follows `The session`: the model line repeats what the
harness states is serving the turn, and the session line is `n/a` — the
marker the claim already carries, not a diagnostic. The harness line names
Codex, with the version the harness itself reports — `codex --version`, where
it answers. A version no surface in the session reports is `n/a`, never a
guessed one.


There is no durable wake
========================

**No actor on this harness outlives the turn that armed it** — no durable
process, no scheduled wake — so `Keep it current`'s split buys Codex nothing:
the mechanical merge has nothing here to run it, and the judgment waits for
a session either way. After `Ready for review`, say
once that the watch is the catch-up look below, and stop.

**The catch-up look is the first read of every turn that lands back on the
pull request.** A turn that returns the session to the pull request — a
resume, a continuation, a user turn about it — starts with the base-currency
read, before anything else the turn was going to do:

    gh pr view <number> --json mergeStateStatus,mergeable

`BEHIND` runs `gh pr update-branch <number>` — `Keep it current`'s merge —
before the turn continues; `DIRTY` is the conflict stop `SKILL.md` writes
under `Where it stops and waits`; `CLEAN`, `DRAFT` and `UNSTABLE` need
nothing. `BLOCKED` and an indeterminate answer are not currency answers: run
the update-branch call anyway, whose own "already up to date" reply settles
what this read has not.

This is the Omp answer arrived at for a different reason. Omp has a timer and
it is measured to die with the session; Codex has no timer this plugin has
found at all. Either way `SKILL.md`'s own rule applies — a watch a surface
cannot keep is worse claimed than skipped — and the never-empty wake slot,
[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md), is the
Claude Code rule this harness does not carry.
