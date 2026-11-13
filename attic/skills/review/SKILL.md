---
name: review
description: >-
  This skill should be used whenever changes are about to be judged ready —
  including when the user says "/review", "review this branch", "is this
  ready", "what do you think of these changes", "give me your opinion on this
  diff", or asks for a second opinion before merging; and on Claude's own
  initiative before marking a draft pull request ready for review
  (`mcp__github__update_pull_request` with `draft: false`), before requesting a
  reviewer (`mcp__github__request_copilot_review`), before declaring a branch
  finished, and before invoking the built-in `/code-review` or
  `/security-review` on a branch. Infers review depth from the diff rather than
  asking for it, dispatches the reviewer panel, and posts the result. Do NOT
  use this skill merely because a pull request is being opened — that is the
  `pr` skill's moment, and a draft opens the conversation rather than ending
  the work.
---

# Review

One skill for one activity. It replaced four verbs — `/deep-review`,
`/quick-review`, `/opinion`, and reaching for the session's built-in
`/code-review` — which existed separately only because a slash command cannot
carry a remembered default. Depth is now **inferred from the diff**, so there
is nothing left to choose between.

Two boundaries define it:

- **Expensive skills are pulled, never pushed.** This never fires on pull
  request *open*. Taxing every trivial branch to catch the occasional serious
  one trains the reflex that makes review worthless — skimming output that
  always appears. It fires on the *asking* moments enumerated in the
  description.
- **Poetry attaches to the posted artifact, never to the analysis.** A finding
  someone has to act on is prose.


Pre-flight
==========

Mode and base branch
--------------------

1. **Base branch**: run `git symbolic-ref refs/remotes/origin/HEAD` and take
   the branch name. If that fails, use `master` when
   `git rev-parse --verify origin/master` succeeds, otherwise `main`. Call it
   `$BASE_BRANCH`.
2. **PR mode or Local mode**: find the pull request for the current branch with
   `mcp__github__list_pull_requests` (`head: <owner>:<branch>`, `state: open`).
   One result means **PR mode**; none means **Local mode**. A pull request
   number given explicitly by the user overrides the lookup.
3. State the detected mode and the inferred depth on one line before
   dispatching, so it is visible which path was taken and why — e.g.
   `Standard review + security-reviewer, PR mode #123 — 640 changed lines,
   touches .github/workflows/`. Note the shape: 640 lines is Standard, and the
   sensitive touch adds a reviewer to that tier rather than promoting it.

Never shell out to `gh`. It is a laptop-only convenience, absent from web
workers entirely, so a `gh` call passes every test on the machine it was
written on and fails invisibly on the other surface. The GitHub MCP is the
client; `curl` against `api.github.com` with the ambient `GITHUB_TOKEN` is the
only fallback, for the endpoints the MCP does not reach.

Gathering the diff
------------------

**PR mode.** Run `git fetch`, then refuse to review a stale tree: if the local
branch is ahead of its remote, stop with "Local changes not pushed. Push
first."; if the remote is ahead, stop with "Remote has new commits. Pull
first." Then read the pull request through `mcp__github__pull_request_read`:

| Method | For |
| ------ | --- |
| `get` | title, body, draft state |
| `get_diff` | the diff under review |
| `get_files` | changed paths, for the depth signals below |
| `get_commits` | commit subjects |
| `get_status`, `get_check_runs` | CI, which feeds the verdict |
| `get_comments`, `get_reviews`, `get_review_comments` | what other reviewers already said |

**Local mode.** Run `git fetch`, then verify there is something to review:
`git log origin/$BASE_BRANCH..HEAD --oneline`, and stop with "No commits ahead
of origin/$BASE_BRANCH. Nothing to review." if it is empty. Assemble the same
data from git — `--name-status` for changed paths, `git diff
origin/$BASE_BRANCH...HEAD` for the diff, `git log --format=%s` for subjects —
and note explicitly that CI status, PR conversation and review threads are
unavailable and therefore cannot be factored into the verdict.


Inferring depth
===============

Depth is read off the diff. Two signals decide it, and one override outranks
both.

**Signal 1 — kind.** Classify the changed paths. The buckets overlap — a
`README.md` is both planning-class and docs-only — so test them **in this
order** and take the first that matches:

1. **Planning-class** — every path is planning-class, and there is at least
   one; a path is planning-class if it lives under `docs/planning/` or
   `docs/proposals/`, or its basename is `README.md` or `CLAUDE.md` anywhere.
2. **Docs-only** — every path ends in `.md`, `.txt` or `.rst`, or is `LICENSE`.
3. **Test-only** — every path matches `*_test.*`, `test_*.*`, `*.test.*`,
   `*.spec.*`, or lives under `**/tests/**` or `**/__tests__/**`.
4. **Code** — anything else.

**Signal 2 — size.** Changed lines across non-generated files, ignoring
lockfiles and vendored trees. The thresholds below are a prior, not a rule: a
thirty-line change to a lock ordering earns a full review, and an eight-hundred
line rename does not.

**The override — a sensitive touch.** If any changed path or hunk touches the
list below, `security-reviewer` runs, **whatever the size or kind**. This is
what killed `/quick-review` properly: the choice a human kept forgetting to
make is now made from the diff.

- authentication, authorization, sessions, tokens, passwords, OAuth, SAML, JWT
- cryptography — ciphers, hashing, TLS, certificates, key material, randomness
- IAM and access policy, in any form: `*.tf` policy or role documents,
  security groups, Kubernetes RBAC, bucket policies
- database migrations and schema changes
- CI and release configuration under `.github/workflows/` — those files hold
  tokens and permissions
- request boundaries: handlers, routes, controllers, deserialization,
  file-path and URL handling
- dependency manifests and lockfiles

The table below reads the *kind* and the *size*; the override is orthogonal to
it and is applied afterwards, never by promoting a row. **Read the rows in
order and take the first that matches**: a small code change is Skim rather
than Standard, because both rows describe it and only the order says which
wins. That settles ties between rows, nothing more. The size feeding the rows
is still a prior and not a rule — where the changed lines understate the work,
as in that thirty-line lock ordering, take the deeper row deliberately and say
so in the mode line. That is a judgment about what the size means, not a
licence the override grants: a sensitive touch adds `security-reviewer` without
promoting the tier.

| Depth | When | Panel |
| ----- | ---- | ----- |
| **Planning** | planning-class | `planning-fitness-reviewer` + `architecture-reviewer`, under the planning rubric |
| **Skim** | docs-only, or under ~50 changed lines | mechanical tier only |
| **Standard** | code or tests, from ~50 to ~800 changed lines | mechanical tier + `logic-reviewer` + `architecture-reviewer` |
| **Full** | over ~800 changed lines | Standard + `security-reviewer` |

Tests sit with code rather than with docs: a test that asserts the bug passes,
and the mechanical tier alone will not notice.

A sensitive touch adds `security-reviewer` to whatever tier the table chose; it
does not promote a fifteen-line diff to a full panel in every other respect.

The user may still name a depth, and a named depth wins — deeper or shallower,
whatever the table would have chosen, and whichever row matched first.
Inference is the default, not a refusal. It does not switch off the override,
though: a named Skim over a diff that touches the sensitive list is a Skim with
`security-reviewer`, and the mode line says so.


The panel
=========

Dispatch through the **Agent tool**, every member in a single message so they
run in parallel. Do **not** pass a `model` parameter: the panel inherits the
session's model. Pinning a model per role was written when the roles differed
in capability by more than they do now, and a pin ages into a cost decision
nobody revisits.

Mechanical tier
---------------

Run the session's built-in **`/code-review`** skill, at an effort level matched
to the depth (low/medium for Skim, medium for Standard, high for Full). It
covers correctness bugs plus reuse, simplification and efficiency cleanups.

**What it does at a given effort level depends on the session's model, and the
difference is large.** `/code-review` resolves a model-family × effort cell, so
the same `medium` is a different reviewer on different models:

- **Sonnet 5** (and the default cell) — angles with an adversarial verification
  vote from `medium` up. This is the behaviour that justifies `/code-review`
  *replacing* a panel of narrow code agents rather than joining one.
- **Opus 4.8** — angles, but no verification below `max`.
- **Opus 5** — `medium` and `high` are **the same cell**: a single careful diff
  pass, no angles, no verification. Only `max` verifies.

Two consequences worth knowing before trusting this tier. On Opus 5 the
Standard/Full split above buys nothing here, because both map to that one cell.
**Depart from the mapping and name `max` when a diff genuinely needs a verified
panel on Opus 5** — no depth in the table selects it, so it only happens if you
ask. And the
precision argument for preferring the built-in over narrow agents only holds
where verification actually runs; where it does not, the judgment tier is
carrying more weight than this section assumes.

See retired note `docs/notes/0001-built-in-review-surface.md` (Git history;
issue #35 is the surviving record of its phases) for the full matrix and the
version it was read from.

If `/code-review` is not available in this session, fall back in order:

1. The `pr-review-toolkit` plugin's agents, if installed — `code-reviewer`,
   `silent-failure-hunter`, `code-simplifier`, and `comment-analyzer`,
   `pr-test-analyzer`, `type-design-analyzer` where they have something to
   evaluate (skip `comment-analyzer` when no comment lines are touched; skip
   `pr-test-analyzer` on a docs-only diff — but never on a test-only one,
   where it is the reviewer with the most to say; skip
   `type-design-analyzer` when no new types or interfaces are introduced).
2. Otherwise one general-purpose agent carrying
   `references/review-guidelines.md`.

Announce a skip in one line, so an absent reviewer is never mistaken for a
clean one — e.g. `Skipping pr-test-analyzer: docs-only diff.`

Judgment tier
-------------

These ship with this plugin, in `agents/`:

- `logic-reviewer` — line-by-line correctness: bounds, races, control flow,
  nil safety.
- `architecture-reviewer` — macro fitness: is this the right shape, does it
  fit, is the complexity proportionate.
- `security-reviewer` — vulnerabilities, including the infrastructure kind:
  permissive IAM, open security groups, unencrypted storage.
- `planning-fitness-reviewer` — planning-class diffs only.

Do not also run the session's built-in `/security-review` alongside
`security-reviewer`. Two agents reading one diff for one dimension is not two
opinions — it is one opinion counted twice, with correlated errors and a longer
findings list to dilute the real one. `/security-review` is the manual twin for
when this skill is not what is wanted.

Every agent receives: the diff and summary, `references/review-guidelines.md`,
the instruction to return findings as severity + `file:line` + evidence, and —
on a planning-class diff — the **Planning-Doc Reviews** section, applied *in
place of* the standard four-tier rubric.

> **Open question (Q5), deliberately unresolved.** Whether `logic-reviewer` and
> `security-reviewer` are better as two roles or one is not settled here. A
> panel pays real structural costs — cross-cutting findings fall in the seam
> between two roles, role framing manufactures findings, synthesis is lossy,
> and instances of one model have correlated errors — against a recall gain
> that shrinks as the single reviewer gets stronger. The crossover point moves;
> this panel was designed on the far side of it and nobody has re-measured.
> Settle it with a measurement, not by inheritance — see
> [`0002`](../../../docs/notes/0002-eval-harness.md) for which harness. Until
> then the two roles stand, and this note is the reason they are worth
> re-examining.
>
> Retired note `0001` surveyed what the built-in did and found the crossover is
> **per model family**, not global: on Sonnet 5 this panel sits on top of a
> verified multi-agent panel, while on Opus 5 at Standard or Full depth it sits
> on top of a single unverified reviewer. It settles nothing about finding
> quality — that is still the measurement in #35; the note is in Git history.


Synthesis
=========

1. **De-duplicate** overlapping findings across agents.
2. **Classify severity** per the four-tier system in the guidelines
   (🔴 Critical, 🟡 Important, 🟢 Minor, 🔵 Nitpick) — or the planning rubric
   on a planning-class diff.
3. **Tag every 🔴 and 🟡** as `[obvious]` or `[judgment]`. 🟢 and 🔵 are not
   tagged; they do not drive the walkthrough.

   **Obvious-fix** requires all three: one sensible action with no competing
   approach worth weighing; a local fix confined to the flagged files, with no
   API or contract change and no cross-cutting refactor; and no design
   trade-off — no performance-versus-clarity, no security-versus-UX, no scope
   question.

   Qualifying: a missing test whose shape is clear from the code under test; a
   swallowed error that should re-raise; mechanical correctness (wrong
   operator, off-by-one with a known bound, a missing nil guard where the
   surrounding code already treats the value as nullable); dead or duplicated
   code; a 🟢/🔵 nit that got flagged 🟡.

   Disqualifying: multiple plausible fixes; an architectural, layering or
   pattern-fit concern; anything touching a public API, schema or migration; a
   performance fix where the approach matters; a security fix where the threat
   model decides the choice.

   **When uncertain, `[judgment]`.** Unnecessary discussion costs one exchange;
   auto-applying a fix the user would have shaped differently costs real work
   to undo.
4. **Factor in CI** from `get_status` / `get_check_runs` in PR mode. In Local
   mode, say that CI is unavailable rather than assuming it green.
5. **Run the Internal Verdict Checklist** from the guidelines. Never display or
   post it.
6. **Verdict**: 👍 or 👎 per the approval criteria.


Display
=======

The audience is a developer at a terminal deciding what to fix.

1. **Overview** — one or two sentences on what the change does.
2. **Concerns & Risks** — every finding, grouped by severity, with `file:line`
   and evidence. Mark each 🔴/🟡 `[obvious]` or `[judgment]`.
3. **Obvious fixes preview** — if any `[obvious]` items exist, a compact
   `Obvious fixes (N):` list, one line each:
   `<severity> path/file.ext:LINE — <the single-sentence fix>`. Omit the
   section entirely when there are none.
4. **Verdict** — 👍 or 👎, with brief reasoning.
5. **Next step** — with `O` = obvious count and `J` = judgment count, emit
   exactly one line:
   - `O > 0, J > 0` — "Apply the [O] obvious fix(es) and discuss the [J]
     judgment call(s) one at a time? (yes/no)"
   - `O > 0, J == 0` — "Apply the [O] obvious fix(es)? (yes/no)"
   - `O == 0, J > 0` — "Discuss the [J] judgment call(s) one at a time, then
     fix in batch? (yes/no)"
   - `O == 0, J == 0` — offer to post instead (see **Posting**). In Local mode,
     say a pull request must exist first.

   When an offer line is emitted, do **not** also offer to post — posting is
   offered after the work is done.

No poems here. No accolades. Keep it terse — poetry belongs on the posted
comment, and this is the analysis.


Walkthrough
===========

Runs only if **Next step** emitted an offer line. Emit it, then **stop and
wait**. An affirmative reply starts the walkthrough; anything else does not,
and the conversation simply continues.

Routing: `[obvious]` items skip **Discuss** entirely and enter the **Execute**
plan as `Fix` rows. **Discuss** runs over the `[judgment]` items only, and is
skipped when there are none.

1 — Discuss
-----------

🔴 first, then 🟡, in the order they appeared. Per issue:

1. **Restate tersely**, at most ten lines:

   ```
   🟡 path/file.ext:LINE — <one-line summary>
   <1–3 short lines of evidence, or why it matters>
   Proposal: <one sentence>
   ```

   No restating the whole function, no long diff blocks, no re-explaining the
   codebase. Past ~5 lines of evidence, link by `file:line` instead. The user
   has already read the review; this is a reminder, not a re-presentation.
2. **Propose, don't lecture.** The `Proposal:` line *is* the discussion. Expand
   into trade-offs only if asked, or where approaches genuinely compete — then
   two or three one-line bullets. **Do not edit code yet.**
3. **Wait** for direction — fix as proposed, fix differently, defer, or skip —
   then record the decision as a todo. Do not start the work.
4. **Move to the next issue without asking permission.** The user opted into
   the whole walkthrough by saying yes. Announce the transition in one line and
   continue. Never ask "shall I continue?"

The only pause is **Wait**. The user can interrupt at any time.

2 — Execute
-----------

1. **Print the plan** as a compact table: action (Fix / Defer / Skip),
   `file:line`, one-line summary — obvious items auto-routed as `Fix`, judgment
   items as decided. Do not ask for confirmation; those decisions were just
   made. State that execution is starting.
2. **Work the todos in order.** For each `Fix`: make the change, run the
   relevant validators, linters and tests for the touched files, and commit it
   as its own focused commit — one logical change per commit, never bundled.
   Defer and Skip produce no commit, just a one-line note.
3. **Stop and ask on conflict.** If the agreed approach turns out not to work —
   it collides with another agreed fix, breaks tests in a way that suggests the
   proposal was wrong, or rests on a wrong assumption — stop, explain, and wait.
   Do not push through.

Then offer to post.


Posting
=======

Only in PR mode, and only when the user asks or accepts the offer. Post with
`mcp__github__add_issue_comment` (a pull request is an issue for comment
purposes). Structure:

```
{one-line summary of the review, max 84 characters}

*Claude {model version, e.g. Opus 5 [claude-opus-5]}*

{summary poem: a formal poem, any style, max 6 lines, summarising the PR}

## Summary

{executive summary of the PR and the review findings}

## Concerns & Risks

{all findings grouped by severity, with evidence}

## Verdict

{👍 or 👎 with reasoning}
```

On a 👍 verdict, and only then, append:

```
## Accolade

{a terse panegyric in formal verse, heroic style, in the Roman / Greek /
Persian / Chinese tradition. If you committed code to this branch, you are a
co-author.}
```

The `*Claude {model version}*` line is **not decoration**. It is how comment
minimisation recognises Claude's own previous reviews; self-identification and
minimisation live or die together. Keep it.

**Exclude the Internal Verdict Checklist.** Every review is free-standing —
never reference a previous one, and never use "Corrected", "Updated",
"Revised" or similar in the one-line summary.

Then hand off to **`pr-threads`**, which owns the rest of the lifecycle:
minimising the previous Claude review, and replying to and resolving threads as
findings are implemented or rejected. Posting findings and then abandoning them
is the two-disconnected-commands failure this skill exists to end. Where
`pr-threads` is not present, do that work here to the same protocol: reply on
the thread stating implemented-or-rejected with the reason, keep it concise and
technical, and resolve it.


Boundaries
==========

- Read-only until the walkthrough. The panel analyses; nothing is edited or
  posted before the user accepts an offer.
- **A review already run on this head discharges the `draft: false` trigger.**
  The description fires this skill before a draft is marked ready; where the
  diff being marked ready is one this skill has already reviewed, that reading
  is done. Commits made since to answer findings, threads or a red check do not
  make it a new diff, and neither does a merge from the base branch that leaves
  the pull request's own diff untouched — only a commit that changes what the
  code does. `undertake` states the same rule at its `Ready for review` step,
  so that a branch it drove is not reviewed twice on the day this skill comes
  back from the attic.
- Never post to GitHub during the analysis and display phases.
- Reading project files, and read-only commands over them, need no permission.
