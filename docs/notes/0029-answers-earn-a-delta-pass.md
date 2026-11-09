# Answers earn a delta pass, not a full round

**Status:** decided, 2026-10-02.
**Resolves:** [#224](https://github.com/jmcvetta/daily-driver/issues/224).
**Amends:** nothing. It builds on
[`0018`](0018-a-briefed-subagent-is-a-reviewer.md) and
[`0021`](0021-the-gate-is-a-read.md), and changes neither.

**Observed.** #224 doubted `review-cycle`'s rule that a commit answering a
review finding never earns another review. On PR #223 the round closed with
the note that both post-review commits answered the round, so no second
round ran. Both commits changed code: they implemented four findings,
including a must-fix. Nobody read those implementations. The classification
of each commit was the author's, and so was the verdict that the fixes were
correct. That is the author-reviews-own-work problem the round exists to
avoid.

The counterweight was real too. A full round per fix cycle re-opens the loop
the rule was written to close, and a reviewer that re-reviews the answers to
its own findings can ping-pong with itself unattended.

## What happened between the question and this answer

The rule #224 doubts was in force for one week.

| Date | Change | Where |
| ---- | ------ | ----- |
| 2026-09-07 | `Does it go again?` classifies each post-review commit as *Answering*, *Changing what the code does*, or *Neither*. Only the second class earns a round. | PR #72 |
| 2026-09-15 07:39Z | #224 opened, citing PR #223's closing note. | #224 |
| 2026-09-15 07:43Z | #225 opened as a `task`: replace the exemption for answering commits with one independent pass over the fix delta. It names #224 as its research. | #225 |
| 2026-09-15 08:12Z | PR #226 merged. It removed the three-way classification and added the stage `Verify the fix delta`. | PR #226 |
| 2026-09-17 | PR #286 gave the stage a route on Claude Code and Codex: one briefed subagent. | `0018` |
| 2026-09-18 | PR #302 replaced the two-pass cap. A pushed fix always earns its pass; the loop ends on the first clean pass; three defect-finding passes in a row is the wall. | `0021` |

So the once-per-diff rule had been replaced thirty-three minutes after the
issue was opened, and before PR #223 itself merged. The issue body still
describes the retired rule. Neither `0018` nor `0021` asked whether a delta
pass is the right design; both took the stage as given. This note is the
decision that closes the question.

## The three doubts, read against the rule in force

**Nobody reviewed the implementations.** `Verify the fix delta` is that
reader. After a batch of fixes is pushed and CI has reported, one reviewer
is given the reviewed SHA, the current SHA, the original findings and their
recorded dispositions. It verifies that each implemented fix solves its
finding and does not regress affected behaviour. The author may not supply
the verdict. Every pushed batch earns the pass that confirms it, and the
record of each pass goes on the pull request.

**The classification was the author's.** It is now content-based, and the
author makes almost none of it. The reviewer compares the pull request's
three-dot content at the reviewed SHA with its content at the current SHA,
so a commit's label, provenance or message decides nothing. Rewritten
history changes nothing either: a missing ancestor is never evidence of no
change. One call stays with the author: a delta that is pure formatting
needs no pass. That residue is accepted here. The brief carries the reviewed
SHA and the current SHA, and on the Claude Code route the reviewer compares
the pull request's content between those two. `review-cycle` describes a
later pass as targeted at the correction delta, so the two SHAs in the brief
are what fix the range it reads. A formatting-only batch pushed last reaches
the gate unread, and a rule that dispatched a reader for a whitespace reflow
would spend a dispatch per round to read nothing.

**It re-opens the loop.** Five bounds hold it closed. The brief forbids a
full pull-request audit and the solicitation of style work. A rejected
finding stays closed unless new evidence defeats the recorded rejection, so
a repeat does not consume a pass. The loop ends on the first clean pass.
Three consecutive passes that each record defects is the wall, reported
with the defects on the pull request rather than pushed through. A full
round still runs only on a material scope change.

## What the rest of the craft does

The shape that shipped is the ordinary one.

- **Gerrit** outdates a vote when a new patch set arrives, unless the
  label's `copyCondition` matches a trivial change kind, and the reviewer
  "may see what has changed since that version by comparing the old patch
  against the current patch". The reviewer re-reads the delta, not the
  change.
- **GitHub** branch protection can "dismiss stale pull request approvals
  when commits are pushed that affect the diff in the pull request". The
  author may resolve their own threads, which is why that setting exists.
- **Google's reviewer guide** allows LGTM with unresolved comments when "at
  least one of the following applies": the reviewer "is confident that the
  developer will appropriately address" them, the comments do not have to
  be addressed, or they are minor. That is trust between two people. An
  unattended round has no second person to trust, so it takes Gerrit's
  shape rather than Google's.
- **Agent review tools** converge on the same delta. CodeRabbit's docs
  describe an incremental review of the changes since its last full review,
  and GitHub describes Copilot code review grouping its findings by whether
  they were resolved since the last review. Neither text was read at source
  for this note; both are recorded from search summaries of the vendors'
  documentation.

## Decided

**The rule in force stands.** A commit that answers a review earns an
independent pass over the fix delta, never a full round. #224's question is
answered by its second option, a lighter pass over just the delta, with the
verdict taken out of the author's hands. No task issue is opened. The
once-per-diff rule as the issue describes it is retired and is not
reinstated.

**The cost of the pass stays unmeasured.** #225 said not to claim measured
savings before measurements exist, and the panel measurement #35 designed
was never run. This note does not reopen either. Whether the pass is worth
its dispatch is a question for a measurement, not for a note.

## Where it landed

This note. No skill changes. The body of #224 keeps its description of the
retired rule as the record of what was asked; this note is the correction.
