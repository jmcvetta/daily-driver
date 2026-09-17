# A briefed subagent is a reviewer — fix-delta verification gains a route

**Status:** decided, 2026-09-17.
**Resolves:** [#283](https://github.com/jmcvetta/daily-driver/issues/283).

**Observed.** `skills/review-cycle/SKILL.md` said to use the harness's named
review surface and "never a bare subagent", on the stated grounds that a bare
subagent "is an ad-hoc dispatch with no review rubric or publication
contract" and inherits nothing. The second half was false in this plugin:
`hooks/hooks.json` runs `hooks/inject-constitution.py` on both
`SubagentStart` and a `PreToolUse` matcher of `^(Agent|Task)$`, so every
subagent already receives the constitution. `a00f9f3`, the commit that added
the rule, was written to make subagents inherit that law on Codex too — it
never claimed a subagent inherits nothing, and the rule as stated overshot
that intent.

The cost was not theoretical. `Verify the fix delta` asks for one reviewer
given the reviewed SHA, the current SHA, the findings and their dispositions.
Omp supplied that, because its named surface is itself a briefable `reviewer`
task agent. Claude Code and Codex declared the pass unavailable, because
`/code-review` and `codex exec review` take a diff target and nothing else.
Since [#226](https://github.com/jmcvetta/daily-driver/issues/226) merged,
`undertake` could not reach `Ready for review` unattended on either harness
after any review that found something — which is every non-trivial pull
request.

## Why it could happen

The rule conflated two properties and demanded both from one artifact:

1. **A rubric and a bounded brief** — what the reviewer is asked to do. This
   is supplied by the dispatching prompt; `skills/review-cycle/references/omp.md`
   already wrote the exact brief the delta pass needs.
2. **A publication contract** — that findings land as resolvable threads
   under a submitted `COMMENT` review. `SKILL.md` already handled a reviewer
   that lacks this, under "Where the review surface returns findings but no
   submitted review".

Neither property requires a *named* surface. What the rule was right to
refuse was an *unbriefed* dispatch — no rubric, no publication route — and
that stays refused.

## Decided

**The reviewer for `Verify the fix delta` is one subagent, dispatched with
the bounded brief `omp.md` already specifies** — not a panel, per
[#225](https://github.com/jmcvetta/daily-driver/issues/225)'s "Use one
reviewer, not an added reviewer panel". The brief is what makes the dispatch
legitimate, and it stays mandatory: the pull request, base branch, reviewed
SHA, current SHA, original findings, dispositions, pass number, and the
instruction not to restart a full audit or solicit style work. The author
still may not supply the verdict — the subagent's result is the evidence, and
the session records it.

- **Claude Code** dispatches one `Agent` tool call carrying the brief, and
  records the pass the same way `Review the head`'s fallback publishes —
  through `mcp__github__add_issue_comment` for the durable record.
- **Codex** dispatches the same brief through the `multi_agent_v1` delegation
  namespace that `skills/undertake/references/codex.md` already uses for
  `Implement`, and records the pass with `gh pr comment --body-file`.
- **Omp** is unchanged — it is the model the other two now follow.
- **`outcome: unavailable` stays reachable.** A dispatch that genuinely
  fails — nothing usable comes back, or nothing comes back at all — is
  recorded as unavailable. A working dispatch is not unavailable by design,
  which is the distinction the retired blanket notice erased.

**The full-review surface at `Review the head` is unchanged.** `/code-review`
and `codex exec review` remain the reviewers there. Whether a subagent panel
should replace them is
[#35](https://github.com/jmcvetta/daily-driver/issues/35)'s open question,
recorded in `attic/README.md`, and it stays open here.

**The two-pass cap, the content-based classification, and the draft-on-
failure behaviour are unchanged.**

## Where it landed

`skills/review-cycle/SKILL.md` (the rule under `Review the head`'s "Review
record, not transcript"), `skills/review-cycle/references/claude.md` and
`skills/review-cycle/references/codex.md` (the fix-delta route),
`skills/undertake/SKILL.md` (the stale citation of the old rule), and
`skills/embark/references/codex.md` (a phrasing echo, reworded for
consistency). `scripts/check-review-cycle-fix-delta-route.py`, wired into
`make check` beside `check-omp-review-cycle-route`, holds the route and the
brief's required elements in place and rejects the retired blanket
unavailability notice.
