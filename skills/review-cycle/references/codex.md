# Codex routes — review-cycle

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in [`claude.md`](claude.md),
Omp's in [`omp.md`](omp.md).

Two of the three parts carry over and one does not. The review surface and the
threads have calls; the wait has none that an unattended session may use, and
that is the stop below.


The review surface
==================

**`codex exec review --base <branch>`**, run from the shell against the branch
that is checked out. `codex review` is the same surface with the terminal UI
around it; the `exec` spelling is the one an unattended session can take.

| Flag | What it selects |
| ---- | --------------- |
| `--base <BRANCH>` | The changes on this branch against its base |
| `--commit <SHA>` | The changes one commit introduced |
| `--uncommitted` | Staged, unstaged and untracked changes |

**`--base` is the one the round wants.** It is the closest thing here to the
three-dot diff `Does it go again?` reasons about, and `--uncommitted` would
review a working tree that `Fix, answer, resolve, push` is about to change
anyway.

**It reviews the checkout, not the pull request.** There is no argument that
takes a pull request number, and nothing is fetched: the branch has to be the
one checked out, and its base has to be a ref this clone has. That is a real
difference from Claude Code, where the round can review a pull request it never
checked out.

**And that costs `Does it go again?` its premise.** That stage defaults a base
merge to `Neither` — not a new diff — *because* the pull request's diff is
three-dot, so a clean merge changes the head and changes nothing the review
would read. Here the review reads a local comparison against a local ref, and
whether `--base` resolves to the merge base or to the branch tip is **not
measured**. Two rules follow, and neither of them is a re-reading of the
default:

- **The classification is unchanged.** `Does it go again?` classifies the
  commits made after the recorded SHA, not what a surface would read, and a
  clean base merge is still `Neither`. A default that flipped per harness would
  buy a review a day on a base branch that moves daily, which is the thing that
  rule exists to refuse.
- **A round that runs for some other reason after a base merge may raise
  findings in code the pull request never touched.** Answer those as findings
  about the base branch rather than about this diff — a reply saying so, and
  resolved — under `Fix, answer, resolve, push`'s *rejected* verdict. Fixing
  them is widening the pull request.

**It takes no effort level**, so `SKILL.md`'s `Name the level` has nothing to
bind — there is no remembered level to override, and the depth judgement is the
surface's. `-c model_reasoning_effort=…` sets a config value for the run rather
than a level the surface remembers between runs, and reaching for it would be
this round choosing a depth by hand on every diff, which `Name the level`
refuses above `high` for the reason it gives there.

**Its findings return locally and must be published as a GitHub review.** They
are not a transcript-only degradation. Give the reviewer the complete history,
reviewed SHA, and current head; the publication route below turns its findings
into the submitted threads that `Fix, answer, resolve, push` answers.

**It is a second agent run, and it is billed as one.** `codex exec review`
starts a fresh session with its own model. That is what makes it a named
surface carrying its own rubric and publication route, rather than an ad-hoc
dispatch with neither, and it is also why the round runs it once per diff
rather than once per push.



Fix-delta verification
======================

**Unavailable on `codex exec review`, not on the harness.** It accepts a base
branch or one commit, not a reviewed-SHA/current-SHA range plus findings and
dispositions; `--commit <SHA>` would verify one commit, not a batch, and
neither substitutes for the required delta pass. The route is the delegation
namespace's `multi_agent_v1` dispatch instead — the same one
[`skills/undertake/references/codex.md`](../../undertake/references/codex.md)
uses for `Implement` — carrying the bounded brief `SKILL.md`'s `Verify the fix
delta` requires: the pull request, base branch, full-review SHA, current SHA,
original findings, dispositions, and pass number. Require it to compare the
pull request's three-dot content at the reviewed SHA with its three-dot
content at the current SHA, exclude changes attributable only to the base
branch, and inspect affected callers. It reports only whether each
implemented finding is solved and any concrete regressions in that delta. It
must not perform a full-PR audit, solicit style work, or supply the verdict —
the session records the result from the delegate's report, never in place of
it.

Publish any findings it raises through this file's `Review history,
publication, and threads` route below, then record the pass with
`gh pr comment <number> --body-file <path>`:

```text
Review verification
scope reviewed: <sha>
pass: <1|2>
verified: <sha>
findings: <finding ids and dispositions>
outcome: <clear|defects|incomplete|unavailable>
defects: <none|concise list>
cap: <open|hit>
usage: <exact value if exposed|unavailable>
```

`outcome: unavailable` stays reachable for a dispatch that genuinely fails —
the delegate returns nothing usable, or does not return at all — recorded as
such rather than guessed at; a working dispatch is not unavailable by design.
Never estimate usage when the invocation does not expose it.

The wait
========

**There is nothing here that waits.** Codex can neither block on the checks nor
wake itself after the turn ends, so this harness is the one `SKILL.md` names
under `How to wait`: *a surface that can neither block nor wake itself cannot
wait*.

So, unattended: **read the checks once, and where they have not all reported,
say so and stop.** Do not review — an unreported check is the thing the wait
exists not to guess at.

| Half | Call |
| ---- | ---- |
| The check runs | `gh api /repos/{owner}/{repo}/commits/{sha}/check-runs` |
| The commit statuses | `gh api /repos/{owner}/{repo}/commits/{sha}/status` |

Both, because `SKILL.md` says *reported* is the union of the two, and one read
of each is the whole of the wait here.

What is not a wait
------------------

Three things look like one and are not. Each is written down because each is
what the next session will reach for.

- **`sleep_tool`.** Codex ships a sleep. `SKILL.md` forbids one outright, in
  the foreground and in the background alike: a sleep is a timer, not a test of
  the thing waited on, and it expires while the checks are still queued as
  readily as long after they went green.
- **`gh pr checks --watch <number>` in the shell.** A blocking foreground watch,
  bounded by the shell tool's own timeout rather than by the checks. It is the
  same case `claude.md` calls *a laptop with neither*, and it is allowed on the
  same condition: **a person is watching the terminal.** Unattended it is the
  shape [`0006`](../../../docs/notes/0006-waiting-for-ci.md) rejects.
- **`codex queue --thread <id> --message <text>`.** It injects a message into a
  saved session, which is most of a durable wake and not the part that matters:
  something outside Codex has to fire it at a time. A wake built on `at` or on
  cron is a workaround, and the constitution says to discuss one before writing
  it.

There is no wake slot
---------------------

[`0010`](../../../docs/notes/0010-the-wake-slot-is-never-empty.md)'s
never-empty wake slot is Claude Code's rule and not this harness's, for the
reason [`0011`](../../../docs/notes/0011-two-harnesses-one-skill-tree.md)
scoped it there: a harness with no durable wake has no slot to fill. Codex is
the second harness that is true of, and it is true here more sharply than on
Omp — Omp at least blocks on the Actions runs, so its wait completes inside the
turn. This one does not wait at all.

`undertake`'s `Keep it current` cadence stops at `Ready for review` here too,
and for the same reason.


Review history, publication, and threads
========================================

Before reviewing, read every submitted review with `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews`. Read the complete thread graph with a
paginated GraphQL `PullRequest.reviewThreads` query, including `id`,
`isResolved`, `isOutdated`, review/comment IDs, replies, SHAs, paths, lines,
and bodies. A REST comments page alone is not complete history and does not
contain the `PRRT_…` ID needed to resolve a thread.

After the review command returns, re-read the head and its diff anchors.
Compare the returned findings with the review history and recorded review
identifier before posting; a resumed run must not duplicate a review already
submitted for that SHA. Put line-specific findings in `review.json` and create
one submitted review:

```json
{
  "event": "COMMENT",
  "commit_id": "<reviewed-sha>",
  "body": "<clean or cross-cutting review summary>",
  "comments": [
    {
      "path": "<path>",
      "side": "RIGHT",
      "line": 42,
      "body": "<finding, with a suggestion block when useful>"
    }
  ]
}
```

Run `gh api --method POST /repos/{owner}/{repo}/pulls/{n}/reviews --input
review.json`. Use `start_side` and `start_line` for a valid range. A clean or
unanchorable review has no `comments` entry and uses the submitted summary.
Never invent an anchor. On changed head, invalid anchor, absent `gh`, or GitHub
failure, retain the findings and report publication as incomplete.

| Operation | Call |
| --------- | ---- |
| Read reviews | `gh api --paginate /repos/{owner}/{repo}/pulls/{n}/reviews` |
| Read threads | paginated `gh api graphql` query of `PullRequest.reviewThreads` |
| Publish review | `gh api --method POST /repos/{owner}/{repo}/pulls/{n}/reviews --input review.json` |
| Reply on a thread | `gh api -X POST /repos/{owner}/{repo}/pulls/{n}/comments/{comment_id}/replies` |
| Resolve a thread | `gh api graphql` with the `resolveReviewThread` mutation |

The identifier trap `SKILL.md` states applies to the last two: the mutation
takes the thread's `PRRT_…` node ID, while reply takes the comment's numeric
ID. The review REST endpoint returns a review ID; record it with the reviewed
SHA and dispositions so later rounds have a stable duplicate check.


Provenance
==========

`codex-cli 0.154.0`, read on 2026-09-12. The subcommands and their flags are
quoted from `codex review --help` and `codex exec review --help`; `sleep_tool`
is read from `codex features list`, where it is `stable` and on. **No review
was run**: that needs credentials this container does not have, so what
`codex exec review` reports and how it is formatted is not measured here. What
is measured is its interface — no pull request argument, no effort level, and
no flag that posts anything.
