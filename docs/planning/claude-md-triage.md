# Triaging the 17KB `CLAUDE.md`

**Status**: record of a completed triage. It says where every part of
`dot-claude/CLAUDE.md` went, and why. The sibling skill issues read it to know
what they inherit.

This was a **copy-forward, not a migration**. `dot-claude` is frozen:
`~/.claude/CLAUDE.md` remains exactly as it is and remains the working setup
until this plugin has earned the swap. Nothing in it was changed, and line
numbers below refer to it as of `dot-claude@5545c99` (2026-08-27) — 361 lines, 16,919
bytes.

Refs: [`plugin-replaces-global-memory.md`](plugin-replaces-global-memory.md) —
Architecture, D1, D2, D4, D9, R3.

## Method

Every item was put through three filters. Failing any one of them is
disqualifying, and the third did most of the work.

1. **Does this change behaviour in most sessions?**
2. **Can you name the moment it fires?** A rule with no attachment point
   decays. *"Always write GoDoc comments"* applies at every line of code,
   therefore at no particular moment, therefore never fires.
3. **Does the harness already say it?** Duplicated guidance costs tokens every
   session and rots silently when the harness changes underneath it.

R3 is why the bar is where it is: the `PreToolUse` hook prepends the whole
constitution to every subagent prompt, so the multiplier is not one per
session but one plus the number of subagents — and this is a workflow built
around delegation.

Result: **16,919 bytes in, 7,427 bytes out**, and most of what survived was
rewritten to name its firing moment rather than merely to state a preference.

## Disposition

### Kept — constitution

| Source | Lines | Note |
| --- | --- | --- |
| Guiding Philosophy | 1–6 | Identity. Merged with the *elegance* principle from Code Quality Standards (222). |
| Style Influences | 224 | One line. It shapes naming and structure in most coding sessions and costs almost nothing. |
| Developer Interface — concise | 29–32 | Kept despite the web harness carrying a "be concise" user preference: that preference is a claude.ai profile setting, absent from the laptop CLI, and the constitution has to hold on both surfaces. |
| Production Safety | 11–21 | Verbatim in substance. Fires rarely; the cost of not firing is unbounded. |
| Sandbox-only dangerous commands | 150–153 | Merged into the same non-negotiables section — it is the same rule at a smaller radius. |
| Code without tests is BROKEN | 64–74 | The flagship rule, kept at full length. It is the one place where compression would cost meaning. |
| I fix it, I don't hide it | 75–78, 163–166 | The source states this twice; merged into one. |
| RTFM | 61–63 | |
| Simplicity is Beautiful | 79–83 | Merged with *do not reinvent the wheel* (157–158) and *I use FOSS* (102–105), which are three phrasings of one instinct. |
| I abjure workarounds | 99–101 | |
| I do not rush | 86–88 | Compressed to a clause. |
| My code fails fast | 95–98 | Merged with *I re-plan when blocked* (92–94) and *I stop and ask questions* (89–91) into **When I hit a wall**. All three fire at the same moment. |
| GoDoc style comments | 84–85, 159–162, 226 | **Amended per D9**: the rule now attaches to *before committing*, and says outright that nothing enforces it. The tempting `PreToolUse` enforcement is withdrawn — matching `git commit` means a regex over a bash command line, and a commit hook that catches most commits is worse than none, because it gets believed. |
| Frequent, focused commits | 39–47 | |
| Commit messages are not Conventional Commits | 169–170 | The PR-title half of the sentence stays, pointing at the `pr` skill, because the contrast is what makes the rule stick. |
| I only add specific files to Git | 112–113 | |
| I will not be lazy | 154–156 | Became **Before I call it done**, and absorbs the *rule* behind the Pre-Completion Checklist (228–234). The per-language commands did not come with it. |
| Package manager only | 109–111, 167–168 | The rule. The 16-line table of per-language invocations (303–318) did not survive as constitution. |
| Planning / delegation | 128–141 | Compressed from three bullet groups to one paragraph. |
| Memory Management | 176–189 | Top tier rewritten: global memory *is* this plugin, so promoting a rule is now a pull request against `daily-driver` rather than an edit on one laptop. |
| Temporary files | 297–300 | One line, with the harness-scratchpad caveat that filter 3 demands. The `.tmp.claude/` permission grant stays in `~/.claude/settings.json`, which cannot travel (constraint 2). |

Two things were **added** that were not in the source:

- **The GitHub client rule** (D2): MCP first, `curl` against the REST or
  GraphQL API where the MCP cannot do the job, and no `gh` for the work
  itself, since it is absent from a web worker altogether. The one exception
  is `gh auth token`: `$GITHUB_TOKEN` is ambient on a web worker but not on
  the laptop, so banning `gh` outright would have left the laptop's `curl`
  fallback with no credential and no way to get one.
- **The verification token** (R1): the constitution ends with a token a
  session can be asked to quote, so that "did it load?" has an answer. The
  hooks and their acceptance test are #15's; the token lives here because the
  file does.

### Kept — skill

| Source | Lines | Goes to |
| --- | --- | --- |
| Claude Helper Tools / PR review workflow | 238–270 | `pr-threads` (#18). This is documentation of `~/.claude/tools/pr-review/`, and D3 retires those scripts one at a time on evidence — the docs move with whichever survive. |
| GitHub Comment Management | 272–277 | `pr-threads` (#18). The load-bearing fact is that minimisation is GraphQL-only, which is precisely why two of the seven scripts keep. |
| `gh` API recipe for PR checks | 279–295 | `pr-ci`, as a **rewrite, not a port** (D2). The recipe is three chained `gh api` calls; the MCP's actions and checks tools cover the same ground, and `gh` is disqualified outright. |
| Pre-Completion Checklist commands | 228–234 | A language-style skill. The rule is constitutional; `standardrb` / `ruff` / `npm run lint` / `terraform fmt` / `go vet` are a lookup table. |
| Package manager table | 303–318 | Same skill. Includes the version-pinning guidance, which is genuinely useful and genuinely conditional. |
| Cinc Auditor/InSpec | 210–219 | Reference under a language-style skill. Nine lines of Ruby-and-AWS specifics that paid rent in every session for nothing. |
| Terraform/OpenTofu | 320–336 | Same, including the count-condition review checklist — which is really a `review` (#19) reference for Terraform diffs. |
| Python / JavaScript / TypeScript / Ruby / Go | 338–359 | Same. Twenty lines of per-language style, none of which fires unless that language is open. |

**No issue owns the language-style skill yet.** #17–#22 cover `pr`, review,
dependencies, bootstrap and the MCP toolsets; the memory skill (D7), the
`godoc` sweep (D9), the `dependabot` response (D11) and this language-style
material have no issue. Four issues are missing, and this is the note that
says so.

### Dropped

| Source | Lines | Why |
| --- | --- | --- |
| Chained-`cd` rules | 114–121 | **D1, a pure deletion.** Both motivations are gone, and the harness states the guidance itself in the Bash tool description: *"Working directory persists between calls, but prefer absolute paths — `cd` in a compound command can trigger a permission prompt."* The *"do not use absolute paths unless necessary"* clause was backwards anyway. |
| Haiku | 195–200 | **D4.** A single mutable file at repo root that every branch rewrites is a guaranteed merge conflict by construction. The poetry survives, on ephemeral artifacts; the tracked file does not. |
| I identify myself as Claude in commit messages | 48–49 | Filter 3. Claude Code appends `Co-Authored-By` on both surfaces. |
| TASK.md tracking | 50–56 | Filters 1 and 3. It fires only in a repo that has a `TASK.md`, and such a repo can say so in its own `CLAUDE.md` — which is exactly what subsidiarity is for. The harness also ships task tooling of its own now. |
| I think before I code | 57–60 | Filter 3, mostly: plan mode is the harness's answer. The part worth keeping — *ask rather than guess* — merged into **When I hit a wall**. |
| I use my tools | 106–108 | Filter 2. *"Using tool scripts is always better than doing things manually"* names no moment, and the harness already prefers its dedicated tools to shell equivalents. |
| I do not state the obvious | 159–162 | Not lost — folded into the GoDoc rule, where it has a moment to hang from. |

## What the sibling issues inherit

- **#15, constitution delivery** — `rules/constitution.md` now holds real
  content, and at the time this was written it ended with a token the
  acceptance test could assert on instead of injecting a synthetic one. The
  token was removed in #89; the test now asserts on a phrase the file says in
  its own prose. The fixture-repo method in that issue works either way.
- **#17, `pr` / `pr-title` / `pr-body`** — the constitution states the commit
  message convention and points at the skill for the PR-title half. Nothing
  from `CLAUDE.md` needs porting into these three; the existing `pr` skill
  already carries the body spec.
- **#18, `pr-threads`** — inherits lines 238–277: the review-tool workflow,
  the thread-reply and minimise recipes, and the node-ID formats
  (`IC_kwDO…`, `PRRT_…`) those recipes depend on.
- **#19, `review`** — **amended in part by
  [`notes/0003`](../notes/0003-repo-local-review-rules.md).** The
  Terraform review checklist (331–336) still goes where the
  `Terraform/OpenTofu` row above sends it — a language-style reference, loaded
  when Terraform is open and costing nothing when it is not. What 0003 forbids
  is the other reading of "inherits": it must not land in `review`'s own
  guidelines, which every agent receives on every review whatever the diff is
  written in. That is the always-on placement the Yor and Checkov rules were
  removed from. The rest of the entry stands — `review` should expect the
  language-style references to be its lookup tables rather than duplicating
  them.
- **#20, issue dependencies** — nothing from `CLAUDE.md`. It is new
  capability.
- **#21, bootstrap** — nothing from `CLAUDE.md`.
- **#22, MCP toolsets** — the constitution now *requires* the MCP for GitHub
  work, which raises the stakes on that measurement: until the MCP runs
  locally, the laptop's only compliant route is `curl`.

## Amending this

The constitution is amended by pull request, and a reviewer is entitled to ask
what an amendment costs: `claude plugin details` reports the plugin's
projected token cost, and R3 is the argument for multiplying it by the number
of subagents a session spawns before deciding the line is worth it.
