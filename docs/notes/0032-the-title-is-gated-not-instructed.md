# The session title is gated by the harness, not instructed by prose

**Status:** decided, 2026-10-07.
**Provenance:** [#572](https://github.com/jmcvetta/daily-driver/issues/572).
Agents on Claude Code (Sonnet) and on Omp (GPT 6 Luna) kept skipping `Title the
session` in `undertake` and `embark`. Three prose fixes did not hold: #316, #386
and #493. On the 2026-10-02 Luna record
(`evals/provenance/omp-gpt-6-luna-2026-10-02-2026-10-02_14-43-15.json`), task
`undertake-09-title-before-claim-omp` with the plugin loaded succeeded in one
replicate of five. The operator reported the same skip on both harnesses on
2026-10-07.
**Implements:** the gate that [`0009`](0009-deny-the-question-widget.md) argues
for, on a different step. #492 left it out on purpose and named it as a separate
item.

Nothing fails when `Title the session` is dropped, so a session that drops it is
never told. The step has no mid-task judgement in it, which is `0009`'s test for
a rule that is enforced rather than instructed.

## Decided

**On both harnesses, two calls are denied until the session carries a title that
was set on purpose:** the session's first comment on an issue or pull request,
and its first dispatch of an implementor.

- **Claude Code:** `hooks/title-gate.py`, in two modes. `post-tool-use` records
  the title when `set_session_title` runs, or when `get_session` reports a title
  in one of `session-title`'s two forms. `pre-tool-use` denies
  `add_issue_comment` and `create_session` until the record exists. The record
  is a file keyed by `session_id`, not the transcript, which Claude Code writes
  asynchronously. The gate applies only where `CLAUDE_CODE_REMOTE` is set.
- **Omp:** the `tool_call` guard in `extensions/daily-driver.js`. It holds a
  `gh issue comment`, `gh pr comment` or `gh api` POST to a `/comments` path, and
  the `task` dispatch. A title is "set on purpose" where the extension
  recorded a `daily_driver_set_session_title` call, or where
  `ctx.sessionManager.getSessionName()` already reads in a form.

**Omp's explicit embark startup barrier is earlier and narrower.** For a
top-level `embark <issue>`, `/embark <issue>`, or registered
`/skill:embark <issue>`, only a successful canonical single-issue `issue://`
read satisfies the identity step. Read-only preparation may precede it, but
does not satisfy it; dispatch and writes stay blocked while identity is
awaiting. When that result confirms the requested epic, the next unrelated
tool call is denied until this session carries `⛵ EPIC #<number> <title>`.
The target metadata comes from the rendered response header, and state follows
the active session branch. The barrier does not classify free-form requests,
issue text or skill examples, and does not change the ordinary
comment/dispatch gate above.

The 2026-10-08 report behind #582 records an automatic Omp title, a later
successful epic read, further instruction reads, and a user correction. It
does not show whether dispatch or a comment would have happened without that
correction. The barrier addresses the observed delay; it does not claim a
demonstrated #573 bypass.

**The denial reason is the instruction.** It says the tool is shut and a retry is
denied the same way, names the calls that set the title, quotes both forms and
names `session-title` as the owner of the budget and the shortening, and says the
denied call succeeds once the title is set.

**The gate checks that a title was set, and the form where it can read the
title.** It never checks the budget or the wording.

**Not gated:** `issue_write` and `gh issue create` (`Open the issue` precedes
`Title the session`), review replies, label and edge writes, the pull request
itself, and Codex, which offers no title surface.

## What it costs

**A session that only closes an issue or comments on a pull request meets one
denial first.** That is intended: `session-title` says to set the title once the
subject is known, and the reason says how.

**The gate's regexes are a second copy of `session-title`'s forms.**
`scripts/check-title-gate.py` and `scripts/check-omp-extension.mjs` assert on both
forms by example, and against that skill's text, so a form change turns the
repository red.

**`CLAUDE_CODE_REMOTE` is a surface check, not a switch.** It is measured, not
documented. If Claude Code renames it, the gate fails open, back to today's
behaviour.

**Omp fails open where it cannot read.** An Omp context with no readable name and
no recorded title call is allowed, with a `console.error` line: a block the model
can only cure by renaming its parent session is the worse failure. An `embark`
subagent in that state is not gated.

## What it does not decide

The two forms, the forty-character budget and the shortening. Those stay
`session-title`'s. Nor does it add an escape-hatch variable, a reminder on
`Skill` or `UserPromptSubmit`, or a gate on Codex.
