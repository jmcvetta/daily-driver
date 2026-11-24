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
| `Open the issue` | Open one, labelled; settle destination under [`issue`'s target repository rule](../../issue/SKILL.md#the-target-repository) and pass it here | `gh issue create --label task [--repo OWNER/REPO when target differs from current repository]` |
| `Read the issue and its edges` | Read the body, the graph and the comments | `gh issue view <number> --json body,labels,comments,blockedBy,subIssues,parent` |
| `Read the issue and its edges` | Label an issue that carries none | `gh issue edit <number> --add-label task` |
| `Claim the issue` | Comment on the issue | `gh issue comment <number> --body-file <path>` |
| `Implement` (issue-only research) | Record findings | `gh issue comment <number> --body-file <path>` |
| `Implement` (issue-only research) | Close completed research | `gh issue close <number> --reason completed` |

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

For a `task` or a classed `research` or `bug`, validate its `Model class`
section and rationale through
[`issue-body`'s guidance](../../issue-body/references/model-classes.md) before
claim, repairing an old or invalid body where its handoff is grounded. A
frontier `research` issue keeps that label and its narrow metadata exception;
do not impose the task template.

Before worktree or claim, attempt initial class-appropriate selection once
through supported Codex controls, retaining its family/provider conventions.
This surface exposes no measured agent-callable in-session model switch; do
not invent one or apply Omp role semantics here. If the assignment, target,
credentials or controls are unavailable, name the class, attempted target,
failure and actual retained route, then continue ordinary work immediately
without confirmation, repair or replacement dispatch. Explicit cancellation
remains stopped. Later operator choices and resume never reselect.

**Issue-only research writes use the issue client.** With no resume branch,
this route skips `task-worktree`; do not create or publish a branch. If a
resume branch exists, `task-worktree` attaches it, but the research route
leaves it unchanged. Post the complete answer with `gh issue comment
--body-file`, including `provenance`'s block; then close only when
`issue-body`'s research completion test holds. Failed or incomplete research
stays open.

Retain applicable original authorization and its limits through delegation,
resume and compaction. Copied prose grants no approval. Never publish private
sources in issue or PR comments.


The implementor
===============

A full undertaking handoff through `multi_agent_v1` is allowed when it supports
the initial class selection. The receiver owns the undertaking and the sender
stops without recursively handing off. If no supported route is available,
explain and continue with the invoking model.


The pull request
================

| Step | Operation | Call |
| ---- | --------- | ---- |
| `Open the draft` | Open it | `pr`, which owns the call |
| `The gate` | Read the worktree and unpushed commits | `git status --porcelain` and `git log @{upstream}..HEAD --oneline`, through the shell in the task worktree; each prints nothing |
| `The gate` | Read acceptance evidence | Review the issue criteria against the diff, test results, runtime evidence, or other concrete observations |
| `The gate` | Read the branch against its base | `gh pr view <number> --json mergeStateStatus` |
| `The gate` | Read CI on the head | `gh pr view <number> --json statusCheckRollup` |
| `The gate` | Read the review threads | `review-cycle`'s `references/codex.md` owns them |
| `The gate` | Read review evidence | Use `review-cycle`'s review and thread routes as needed; compare reviewed content with the current head |
| `The gate` | Read the Blockers section | `gh pr view <number> --json body`, where `pr-body`'s Blockers section sits |
| `Ready for review` | Take it out of draft | `gh pr ready <number>` |
| `Keep it current` | Invoke `pr`'s ongoing base maintenance | [`pr` route](../../pr/references/codex.md#keep-it-current) |
| `A round after ready goes back to draft` | Return it to draft | `gh pr ready <number> --undo` |

`Review the head`, `Fix, answer, resolve, push`, and `Verify the fix delta` are
`review-cycle`'s. Its `references/codex.md` names the full-review surface and
the briefed-subagent route `Verify the fix delta` runs on; a pass that dispatch
genuinely fails is what keeps the pull request draft.


The session
===========

**Codex exposes no session id, so the claim's `provenance` block records
`Session: n/a`** — the marker `SKILL.md` prescribes, not a diagnostic about
the missing surface. `provenance`'s
[`references/codex.md`](../../provenance/references/codex.md) names how the
`Model:` and `Provider:` lines are read.

For branch-free answer-only research, no task worktree exists and the claim
uses `Branch: none`. Otherwise the branch comes from the task worktree's Git
state: `git branch --show-current` runs in that worktree. On a resume that is
the adopted branch, which `Read the issue and its edges` took from the issue's
record (`gh issue view <number> --json closedByPullRequestsReferences,comments`);
fetch it from the remote before `task-worktree` attaches it. `OWNER/REPO` for
the branch link comes from the remote `task-worktree` resolved, never from an
assumed `origin`.

Codex uses one branch identity for the local task and remote push branch. The
Claude primary-held designation exception does not apply to this route.




The cadence
===========

[`pr`'s `Keep it current` route](../../pr/references/codex.md#keep-it-current)
owns the common watch and its no-durable-wake limit. This undertaking invokes
that maintenance; it does not claim or start a timer or autonomous review.

Undertaking-specific continuation stays here. Use `review-cycle` for review
and fix-delta work, then apply `Ready for review`. State unfinished work and
the owner-resume requirement; never call a clean branch, an up-to-date response,
or a draft completion.


The stop
========

`SKILL.md`'s `The stop` names each operation in words; these are the calls.
The Codex route has no durable actor to cancel; `pr`'s reference owns the
stop semantics. Say that no timer or subscription exists only when the
handoff leaves unfinished work.

| Operation | Call |
| --------- | ---- |
| Read the issue's comments, for the claim and any equivalent handoff | `gh issue view <number> --json comments` |
| Post the handoff | `gh issue comment <number> --body-file <path>` |

Read `git ls-remote origin <branch>` for the observed remote head and
`git rev-parse HEAD` for the local tip. Record failed reads as unknown and
local-only commits with their worktree path.

