# Daily Driver: Replacing the Global CLAUDE.md

**Status**: living document. Kept current as the work proceeds, and amended by
pull request — the same process it specifies for the constitution itself.

## Goal

Make `daily-driver` the *entire* Claude environment, so that a session
behaves identically whether it runs on the laptop CLI or on a Claude Code web
worker.

Today the environment is split. `dot-claude` *is* `~/.claude` — versioned, but
deployed only to the laptop. It holds the 17KB engineering philosophy plus
commands, agents, hooks and shell tooling. The plugin holds one skill. Web
workers get none of it.

The problem is therefore not that the global rules are unversioned. They are
versioned. The problem is **reach**: a repo of dotfiles is deployed by being
checked out onto a machine, and a web worker is not that machine. A plugin is
deployed by being installed, which both surfaces can do.

After this work, the plugin holds everything portable. `dot-claude` survives as
a laptop-settings repo and nothing more.

## Platform constraints

Established by reading the plugin and hooks references, not by assumption.

1. **A plugin cannot ship a `CLAUDE.md`.** Per the plugins reference: *"A
   `CLAUDE.md` file at the plugin root is not loaded as project context.
   Plugins contribute context through skills, agents, and hooks rather than
   CLAUDE.md."*

2. **Plugin `settings.json` supports only `agent` and `subagentStatusLine`.**
   So `permissions`, `model`, `effortLevel`, `editorMode` and `autoMode` cannot
   travel in the plugin. They stay in `~/.claude/settings.json`. This is fine —
   they are harness configuration, not memory, and a web worker neither needs
   nor wants the laptop's allowlist.

3. **Always-on context in the main session comes from a `SessionStart` hook**
   emitting
   `hookSpecificOutput.additionalContext`. The plugin ships `hooks/hooks.json`
   plus a script that reads exactly one file,
   `${CLAUDE_PLUGIN_ROOT}/rules/constitution.md` — not a glob over that
   directory. D12 feeds the subagent hook from the same file, and a glob is how
   the two injection points would silently diverge the day a second file landed.
   Being harness-executed, the script behaves the same on CLI and web.

4. **`InstructionsLoaded` and `SubagentStart` are observation-only.** Neither
   supports decision control, so neither can inject or amend instructions.

5. **`SessionStart` `additionalContext` does not reach subagents.** The docs
   are silent on this; it was measured (see R2). A `CLAUDE.md` reaches both the
   main session and its subagents, so hook-delivered context is strictly weaker
   unless paired with a second hook.

6. **`PreToolUse` can rewrite tool input** via
   `hookSpecificOutput.updatedInput`. This is what closes the gap in
   constraint 5: a hook matching the `Agent` tool prepends the constitution to
   every subagent prompt. Measured, not assumed.

7. **Repo-level installation** is `.claude/settings.json` with
   `extraKnownMarketplaces` + `enabledPlugins`, applied once the folder is
   trusted. This is per-project, so every repo needs the stanza — a job for a
   `bootstrap` skill.

8. **Only `Stop` can hand the model another turn — and only via its exit
   code.** A hook is a shell command, and the way back into the conversation is
   narrow. `PreCompact` and `PostCompact` *"can't make decisions that affect
   compaction; they can only observe it and emit side effects"*; `SessionEnd`
   *"can't block the session end or affect it"*; neither supports
   `additionalContext`. `Stop` is the exception, and the distinction is exact:
   **its JSON decision fields are not read** — *"Claude Code doesn't read any
   decision from your hook's JSON output"* — but **exit code 2 is**, documented
   as *"Prevents Claude from stopping, continues the conversation"*. So a duty
   needing the model's judgement at one of these moments is discharged by the
   hook script itself at compaction or session end, and by a `Stop` hook exiting
   2 when a later turn is acceptable. This constraint is what reshapes D7.

## Architecture

### Three layers

Named, not numbered — a layer whose name has to be decoded is a layer nobody
will remember the rules for.

| Layer | Contents | Cost |
| ----- | -------- | ---- |
| **Constitution** | Injected into every session by the `SessionStart` hook. Identity and non-negotiables only, plus a one-line index of the plugin's skills. | Every session, forever |
| **Skills** | Fired by activity: PR workflow, review, memory, language style, delegation. | Only when triggered |
| **References** | Files inside skills, read on demand. | Only when read |

"Constitution" is chosen deliberately, and earns its weight: supreme law, always
in force, and amended only by a deliberate reviewable process. Under D7 that
process is literally a pull request against this repository.

**There is no line limit.** A cap would be arbitrary and would get gamed by
compression rather than by cutting. Admission is governed by filters instead —
two here, and a third from D1:

*Does this change behaviour in most sessions?*

And, discovered while triaging `/godoc`:

> **A rule with no attachment point decays. A rule attached to a moment
> survives.**

"Always write GoDoc comments" applies at every line of code, therefore at no
particular moment, therefore never fires. "Before committing, GoDoc-comment
every exported symbol you added" hangs off an event that recurs constantly. Any
constitutional candidate for which no firing moment can be named is probably
decorative.

And a third, from D1:

> **Do not legislate what the harness already says.**

### Skills, not commands

The observation that drove this: of ten commands in `dot-claude`, roughly three
are remembered. That is a design signal, not a memory failure. Each command is
either a duty that should fire on its own, a rule already stated elsewhere, or a
genuine on-demand task. Only the third kind stays invocable.

Two house rules follow:

1. **Every skill description enumerates Claude's own tool calls as triggers**,
   not only human phrasings. The existing `pr` skill already does this and is
   the template.
2. **Skill is the knowledge; hook is the guarantee it gets consulted.** Where
   description-matching is merely a hope, a `PreToolUse` hook makes it a
   certainty.

## Decisions

### D1 — Delete the chained-`cd` rules outright, replacing them with nothing

Both original motivations are gone: permission approval (auto mode) and cwd
confusion (the harness now reports working-directory changes).

The first instinct was to replace them with a constitutional line preferring
absolute paths, since the underlying behaviour has not entirely vanished — the
working directory does still get reset, and `cd` in a compound command can
still trigger a prompt. But the harness **already says so itself**, in the Bash
tool description: *"Working directory persists between calls, but prefer
absolute paths — `cd` in a compound command can trigger a permission prompt."*

Legislating it again would buy nothing and cost tokens in every session, so this
is a pure deletion:

- Delete the "no chained `cd`" rule.
- Delete the "do not use absolute paths unless necessary" rule, which was
  backwards anyway.
- Delete `hooks/block_chained_cd.sh`.
- Add nothing.

That yields a third admission filter, alongside the two in the architecture
section:

> **Do not legislate what the harness already says.** Duplicated guidance costs
> tokens every session and rots silently when the harness changes underneath it.

This filter deserves suspicion when the rest of the 17KB is triaged. A rule
written years ago to compensate for a weaker harness is exactly the kind that
survives on inertia — and the whole point of an amendment being a reviewable
pull request is that inertia has to be argued for.

### D2 — Adopt the GitHub MCP everywhere, including locally

This solves the CLI/web portability problem by deletion rather than
abstraction: one code path, both surfaces.

Second payoff: **hook enforcement becomes reliable.** A `PreToolUse` matcher on
`mcp__github__create_pull_request` is an exact string match. The `gh`
equivalent is a regex over a bash command line, defeated by a wrapper, a
heredoc, a variable, or a stray space.

Costs, acknowledged:

- ~55 tool definitions in context. The server's `--toolsets` flag is the
  mitigation, but *which* toolsets is deliberately not settled here: Q6 answers
  it by measurement, after a fortnight with everything enabled. Naming a list
  now would also be wrong on its face — `pull_requests,issues,repos` omits the
  actions and checks tools that D5's `pr-ci` is defined in terms of, and a
  toolset chosen before the workflow exists is the premature decision Q6 is
  written to avoid.
- Local auth needs a PAT or `gh auth token`; web is wired automatically.
- Gaps remain: comment minimisation, `gh run watch`, log tailing.

`gh` stays installed as an escape hatch, demoted from default.

Constitutional line: *GitHub work goes through the GitHub MCP. Where the MCP
cannot do the job, use `curl` against REST with the ambient `GITHUB_TOKEN` —
not `gh`, which exists only on the laptop (see D13). Say which, and why.*

### D3 — Retire `pr-review` scripts one at a time, on evidence

An earlier draft of this section retired six of the seven outright, on a table
mapping each to a plausible MCP tool. That was too fast. Only two of the seven
verdicts rested on evidence; the rest rested on a tool *name* looking like it
would do the job, which is not the same as it doing the job.

So the rule for this directory is a bar, not a list:

> **A script is retired when its replacement has been demonstrated on a real
> PR — not when a plausibly-named MCP tool exists.**

Current state of knowledge, honestly labelled:

| Script | Status |
| ------ | ------ |
| `pr-minimize-comments.sh` | **Kept**, ported under `skills/pr-threads/scripts/`. `minimizeComment` is GraphQL-only and unexposed by the MCP. A real capability gap. |
| `pr-minimize-previous-claude-comments.sh` | **Kept**, ported, same gap. |
| `pr-find-claude-comments.sh` | **Kept**, ported. It returns GraphQL node IDs (`IC_kwDO…`); `search_issues` does not. The surviving minimize scripts consume exactly those IDs, so retiring their supplier while keeping them makes no sense. |
| `pr-fetch-data.sh` | **Retires.** Thread IDs *are* obtainable — measured on `#25`, 2026-09-06. `pull_request_read` with `get_review_comments` returns each thread's `id` as `PRRT_…` directly. Nothing else the script gathered lacks an MCP route. |
| `pr-reply-thread.sh` | **Retires**, unblocked by the row above. `add_reply_to_pull_request_comment` plus `resolve_review_thread` are equivalent, with the identifier caveat below. |
| `pr-post-comment.sh` | **Likely retires.** `add_issue_comment` is a straightforward equivalent; still wants one demonstration. |
| `pr-get-current-branch-number.sh` | **Likely retires**, but not free: there is no "PR for the current branch" MCP call, so it becomes `list_pull_requests` filtered by head ref. |

Three things follow. First, the dependency chain matters more than the
individual mappings: minimisation is a genuine gap, minimisation needs node IDs, and node
IDs come from a script. Cut the middle of that chain and the surviving ends stop
working — the kind of silent breakage that only shows up months later when an
old review comment fails to collapse.

Second, **the client these scripts use is a retirement condition of its own,
and the table above does not look at it.** Every verdict there weighs one
question — can the MCP do this? — while D13 measures a second: `gh` is absent
from a web worker altogether. A script that keeps on MCP-gap grounds and
reaches for `gh` still fails the one thing this plan exists to achieve, and
fails it invisibly, on the surface nobody develops on. So a keep is
conditional:

> **A script that survives on an MCP gap must reach GitHub the way both
> surfaces can.** The gaps named above are GraphQL — `minimizeComment` and the
> node-ID queries alike — so the portable client is `curl` against
> `api.github.com/graphql` with the ambient token, which is where D13 lands for
> the same reason.

Whether that means rewriting or merely confirming is unchecked: these scripts
predate this plan, and *which* client each already uses has not been read.
Reading them is a step in the port, not an assumption to make here. What is
settled is the bar — a survivor ships only once it runs on both surfaces —
because the alternative is a keep that passes every test on the machine where
it was written.

**Answered by the port: rewriting.** All seven reach for `gh`, so every
survivor was rewritten against `curl`. Two findings from doing it are worth
more than the verdict.

**The portable client above is not portable, and the paragraph naming it is
wrong.** Measured in a web worker on 2026-09-06: `POST
api.github.com/graphql` with the session's ambient `GITHUB_TOKEN` refuses
*every* operation — `minimizeComment`, a `reviewThreads` query and
`addPullRequestReviewThreadReply` alike — with

> This GraphQL query is not enabled for this session — only the pinned set of
> PR-review operations is served.

The token is brokered, not personal, and the gate is the broker's. REST over
`curl` is unaffected, which is why the node-ID supplier ports cleanly and the
mutation does not. D13 had already recorded this about *its* container in
passing; what is new is that it defeats the retirement condition this section
states as settled, because the gap the condition was written to protect —
minimisation — is the one thing on the wrong side of the gate.

So the bar needs its second clause, and it is a narrower thing than "runs on
both surfaces":

> A survivor must **fail legibly** where it cannot run. Minimisation is a
> laptop capability on a personal token; `skills/pr-threads/scripts/` reports
> the HTTP status and GitHub's own message for every failure, and names the
> gate specifically when the message is the gate's. A script that cannot be
> portable is acceptable. A script that is silently non-portable is what this
> plan exists to prevent, and an obscure failure on the surface nobody
> develops on is the same defect wearing a different coat.

Detecting the gate by the *absence* of a `data` key was the first attempt and
is wrong. Measured 2026-09-06: the broker answers ahead of GitHub, so a
deliberately invalid token draws the same 403 and the same bare `message` as a
valid one. The shape identifies the surface, not the fault — so a stale token
on the laptop would have been diagnosed as "run this from the laptop". Match
the gate's text; report everything else as what it is.

**The identifier trap the MCP route replaces `pr-reply-thread.sh` with.** The
two MCP calls want different identifiers, and only one of them is a field.
`get_review_comments` gives the thread's `id` as `PRRT_…`, which
`resolve_review_thread` takes; `add_reply_to_pull_request_comment` wants a
*number* that appears nowhere in the response — it is the `#discussion_r…`
suffix of the comment's `html_url`. The thread ID is therefore the identifier
that is present, conveniently typed, and wrong for replying. Recorded in
`skills/pr-threads/SKILL.md`, where the calls are actually made.

Third, the surviving directory still needs its governing rule, which is
unchanged and is the point of the exercise:

> **A skill's `scripts/` holds only what the MCP demonstrably cannot do, and
> each script's header says why it exists.**

A self-liquidating directory. As the MCP grows, scripts get deleted — but each
deletion is earned by a demonstration, not by an assumption.

**Naming collision, introduced by `master`.** The plugin *is* the repository
root (`"source": "./"`), and `master` now carries `scripts/check-manifests.py`
— repository tooling that runs in CI, not plugin runtime. A single root
`scripts/` would mean two unrelated things, and the self-liquidating rule above
would read as though it governed the CI helper, which it must not: that script
has nothing to do with the MCP and is never going away.

So they separate by location, and the rule follows the runtime ones:

- `/scripts/` — repository tooling. Runs in CI, on the repo itself. Governed by
  nothing in this document.
- `skills/<skill>/scripts/` — plugin runtime. Governed by the rule above, owned
  by the skill that calls it, and deleted when that skill no longer needs it.

Putting runtime scripts beside their skill is better than a shared directory
anyway: it makes the owner obvious, and it means a skill and its scripts are
retired together rather than leaving orphans behind.

### D4 — Retire the haiku convention; keep poetry

`HAIKU.md` is a single mutable file at repo root that every branch rewrites.
That is a guaranteed conflict on every merge, by construction. A merge driver
(`merge=ours`, or union) would trade the conflict for a silently wrong file —
a workaround, and not worth it.

Poetry was never the cost; the tracked file was. PR bodies and review comments
are per-branch and never merged, so they carry poetry for free.

> **Poetry belongs on ephemeral artifacts, never on tracked files.**

Removals are wider than the file itself. `HAIKU.md` has accreted special-case
handling across the review tooling, all of which goes with it:

- `commands/haiku.md`
- the `Haiku` section of `CLAUDE.md`, and the "plans always include a step for
  updating the haiku" clause
- `HAIKU.md` from both repos
- the `HAIKU.md` skip rules in `deep-review.md` (three of them) and the
  "not subject to review at all" carve-out in `review-guidelines.md` — both
  exist only because the file changes on every branch
- the "Do NOT reuse the haiku from `HAIKU.md`" clause in `post-deep-review.md`

That the convention needed a carve-out in the review rules is itself evidence
against it.

**Poetry survives, and is already fully specified — no new spec needed.** The
existing convention is more precise than the "salutation or envoi" framing that
prompted this question, because it is both, and the second one is *earned*:

| Where | Spec | Source |
| ----- | ---- | ------ |
| PR body | A brief poem, classical style, conveying the gist of the PR, in italics. | `skills/pr/SKILL.md` |
| Review comment, opening | A formal poem, any style, max 6 lines, summarising the PR. | `post-deep-review.md:36` |
| Review comment, closing | Only on a 👍 verdict: a terse panegyric in formal verse, heroic style, in the Roman / Greek / Persian / Chinese tradition. | `post-deep-review.md:57` |
| Review *findings* | *"No poems. No accolades. Keep it terse."* | `deep-review.md:285` |

The distinction in the last row is the load-bearing one: poetry attaches to the
*posted artifact*, never to the analysis. A finding someone has to act on is
prose.

One coupling to preserve while porting: the review comment's `*Claude {model
version}*` self-identification line is not decoration. It is how
`pr-minimize-previous-claude-comments.sh` — one of the two scripts surviving D3
— recognises its own comments. Self-ID and the minimise script move together or
not at all.

### D5 — The PR skill splits three ways

- `pr` — orchestrator for *opening*: branch guard, existing-PR check, draft
  state, issue references. Invokes the other two.
- `pr-title` — Conventional Commits, concise.
- `pr-body` — one-line summary (85 char limit), salutation, Summary, detail,
  unopinionated.

Real sibling skills with their own descriptions, so that a decision to edit a PR
body fires `pr-body` directly without routing through `pr`. Skill names are flat
within a plugin. Cost is two extra descriptions in context; negligible.

Further siblings: `pr-threads` (reply, resolve, minimise) and `pr-ci` (drive to
green).

### D6 — Collapse four review verbs into one skill

`/quick-review` states outright that it *is* `/deep-review quick` — *"Do not
duplicate the workflow here; follow `/deep-review` as the single source of
truth."* It exists only because a slash command cannot carry a remembered
default. A skill can. Add `/opinion` and the session built-in `/code-review`,
and there are four verbs for one activity, which is precisely why none of them
is remembered.

One `review` skill:

1. **Fires on its own moments** — about to open a PR, branch declared finished,
   about to request review, "is this ready".
2. **Depth is inferred, not typed** — from diff size and from what the diff
   touches. Anything in the sensitive list (auth, crypto, IAM, migrations)
   makes `security-reviewer` mandatory regardless of size. This kills
   `quick-review` properly, by automating the choice rather than deleting the
   alias.
3. **Feeds `pr-threads`** — findings are posted, then the thread lifecycle
   protocol runs. One pipeline, not two disconnected commands.
4. **Audit the 409 lines for rot** — hardcoded model assignments (the "two Opus
   reviewers" split will age badly), `Task` invocation syntax, `gh` calls, and
   overlap with the `code-review` and `security-review` skills that now ship in
   the session.

Open empirical question, narrowed in Q5: not whether the panel as a whole
earns its place — the cheap mechanical tier plainly does — but whether the two
Opus judgment reviewers are better as two roles or one.

### D7 — `/save` and `/restructure` become a memory skill, fired at compaction

"Update project and local memory files" is a duty, not a command — and
remembering to save memory is the one thing that should never require
remembering.

`PreCompact` is the correct *moment*: context is about to be discarded, which
is exactly when memory should be written, and `SessionEnd` is the backstop for
sessions that end without compacting.

**The obvious wiring does nothing at all.** Constraint 8 is the reason:
`PreCompact` and `SessionEnd` cannot hand the model a turn, so a hook
registered on either fires a shell command into a conversation that is already
over. Written that way the memory skill would never once run — failing exactly
like R1, silently, in the direction nobody checks, the first evidence being a
memory file that stopped growing months ago.

There are two working mechanisms, and the cheap one covers the common case.

**`Stop`, exiting 2 — the session writes its own memory.** Constraint 8's
exception: exit code 2 *"prevents Claude from stopping, continues the
conversation"*. The hook's stderr becomes the instruction, and the session
discharges the duty with the context it already holds — no nested invocation,
no second set of credentials, and the memory is written by the reasoning that
produced it rather than reconstructed from a transcript. This is strictly
better than the fallback wherever it applies.

Two things it needs. `Stop` fires after *every* response, so the hook must be
guarded — write only when the transcript has grown past a threshold since the
last save, or the session becomes an unusable nag. And a `Stop` hook that
unconditionally continues loops forever; the reference documents a flag for
exactly this (`stop_hook_active`, name to confirm when building), and the guard
must honour it.

**A headless pass — the fallback for moments `Stop` cannot reach.** Compaction
can arrive mid-turn, and a session can end without a final response, so neither
`PreCompact` nor `SessionEnd` is covered above. There the hook does the work
itself: `transcript_path` is a common input field present on every event, and
the script spends it on a headless `claude -p` that reads the transcript and
edits the memory files directly. Costs, accepted: a nested invocation with its
own latency and credentials — ambient on a web worker, the first hook to need
any on the laptop — and a memory prompt that lives in the hook script rather
than in the skill.

Either way **the skill is no longer the thing that fires**, so it stays
invocable as its own manual twin, for when the automatic path is not what is
wanted. The same shape D9 gives `/godoc`, for the same reason.

*(`PostCompact` was considered as a cheaper route than the headless pass — drop
a marker before, inject "memory was not saved, write it now" after. It does not
support `additionalContext`, so it cannot. Checked, not assumed.)*

`/restructure` is the same skill's other half — compaction of memory rather
than capture — triggered by a size threshold.

**The memory model loses its top tier.** Global `CLAUDE.md` becomes the plugin,
so "restructure your three memory files" now means three different things:

- project `CLAUDE.md` hygiene — unchanged
- `CLAUDE.local.md` compaction — the automatic half, driven by the
  compaction hook rather than by the session
- global rules — a PR against `daily-driver` instead of against
  `dot-claude`

The third is a relocation, not an upgrade: lessons-learned promotion is already
a reviewable commit today, because `dot-claude` is already a repo. What changes
is where the commit lands and, consequently, who sees the result — a rule
promoted into the plugin reaches web workers, a rule promoted into `dot-claude`
reaches one laptop.

One genuine gain does follow: the `pr` and `review` skills end up governing
changes to the constitution itself. Pleasingly self-hosted, and a real test of
whether the thing works.

### D8 — `/copilot` dies; its protocol is harvested

No Copilot subscription. But four sentences took thought and generalise to any
reviewer — human, Claude Approvals, or whatever bot comes next: *reply on the
thread, state implemented-or-rejected, resolve it, keep it concise and
technical, and re-resolve repeat findings with the identical message.* Those
move into `pr-threads`. The Copilot framing is the disposable half.

### D9 — `/godoc` survives as a manual sweep

It is a workaround for a rule that does not fire, and that is accepted
knowingly. The fix is at the source: give the rule an attachment point —
*before committing* — so that it hangs off a moment recurring often enough to
be worth stating.

The tempting second half was a `PreToolUse` hook enforcing it, and that half is
withdrawn. Matching `git commit` means a regex over a bash command line, which
is the mechanism D2 rejects three sections earlier as *"defeated by a wrapper, a
heredoc, a variable, or a stray space"* — and a commit hook that catches most
commits is worse than none, because it gets believed. What rescued D2 from that
regex was an exact MCP tool name to match on; there is no MCP commit tool, so
nothing rescues this one. The rule therefore rests on its attachment point and
on compliance, and says so rather than implying an enforcement that does not
exist. Then `/godoc` is what it should have been all along — a sweep over *old*
code, a legitimate on-demand task — rather than the primary mechanism for new
code.

### D10 — `review` never fires automatically on PR open

Rejected, and the rejection sets a boundary the rest of the design needs.

"Skill, not command" is about *duties that decay because nobody remembers to
invoke them*. It is not a mandate that every skill self-trigger. Review is
expensive in time, tokens and attention; a skill that costs that much should be
**pulled, not pushed**. Firing it on every PR open would tax every trivial
branch to catch the occasional serious one, and would train exactly the reflex
that makes review worthless — skimming the output because it always appears.

There is also a workflow reason. PRs open as **drafts** (D5). Opening a draft is
the start of the conversation, not the end of the work; review belongs on the
draft when the branch is actually ready, which is a judgement call, not an
event.

> **Cheap skills may push. Expensive skills must be pulled.**

So `review` keeps an explicit invocation, and its self-triggering descriptions
(D6.1) cover the *asking* moments — "is this ready", "review this branch",
"about to request review" — never the mechanical act of opening a PR.

### D11 — `dependabot` is a response, not a schedule

The premise behind Q2 was wrong. Dependabot **is already the Routine**: GitHub
runs it from `.github/dependabot.yml` and opens PRs on a schedule of its own.
Wrapping it in a second scheduler would be one cron job watching another.

What `dependabot.md` actually encodes is the *response* — batch the open
dependabot PRs, upgrade in a worktree, validate, open one consolidated PR. That
is a duty triggered by a condition (open dependabot PRs exist), which is exactly
the shape of a skill: it fires when the condition is noticed during ordinary PR
work, and stays invocable for when it is not.

Since this was written, `.github/dependabot.yml` has landed on `master` —
github-actions and terraform ecosystems, weekly — so the schedule this decision
declines to duplicate is now live in this repository too.

### D12 — The constitution is one file with two injection points

Forced by measurement rather than chosen; R2 carries the evidence and the
method. It is restated here because the Decisions list is where an implementer
reads their instructions, and a decision that exists only inside a risk section
is a decision waiting to be missed.

The constitution ships as a single file in the plugin, read by two hooks:

1. `SessionStart` → `hookSpecificOutput.additionalContext`, for the main
   session.
2. `PreToolUse` on the `Agent` tool → `hookSpecificOutput.updatedInput`,
   prepending the same text to the subagent prompt.

One source of truth, two delivery paths, no drift. Shipping only the first is
the silent regression R2 describes; constraint 3 is worded to keep the second
reading the same file rather than a directory; and R3 records what the second
path costs.

### D13 — A relationship skill, wanted; the MCP is the gap, not the API

Wanted, and decided here rather than deferred. Dependencies are a long-wanted
capability, now available, and intended for constant use — which answers the
scope question that would otherwise have gated the decision.

What the MCP surface actually offers, checked rather than assumed:

| Relationship | Status |
| ------------ | ------ |
| **Sub-issues** (parent/child) | Fully exposed. `sub_issue_write` adds, removes, reprioritises and re-parents; `issue_read` reads `get_sub_issues` and `get_parent`; `issue_write` can create an issue directly under a parent — **including cross-repo**, via `parent_owner` / `parent_repo`. |
| **PR closes issue** | Readable, and *only* here — REST has no such field. `issue_read` returns `closed_by_pull_requests` as a count plus up to five references. |
| **Blocked-by / blocking** | **Not exposed by this MCP** — no tool, no field. |

**The API does expose blocked-by / blocking programmatically**, and that
documentation now has an address:
[`jmcvetta/career`, `docs/issue-dependencies.md`](https://github.com/jmcvetta/career/blob/master/docs/issue-dependencies.md).
It carries the endpoints, the `issue_id`-is-the-database-id trap, cross-repo
edges, and a probe table of what the API refuses. Start there; do not
rediscover it.

So the gap is the **MCP's, not GitHub's**, and the shape follows: dependencies
become the first new resident of a skill's `scripts/` under D3's rule — a
script that
exists because the MCP demonstrably cannot do the job, with a header saying
exactly that and a plausible expiry date for when the MCP catches up. That is
the self-liquidating directory working as designed rather than accumulating.

**Answered: issues only.** Probed 2026-09-06 and recorded in that document
under *Pull requests are not in this graph*. Both graphs refuse a pull request
at both ends — dependencies with "Source issue may only be an issue" and
"Target issue may only be an issue", sub-issues with "Parent may only be an
issue" and "Sub issue may only be an issue".

So the scope narrows to one sentence: **this is an issue-graph skill that PRs
merely reference.** The PR half reduces to `closed_by_pull_requests` and the
`Closes #123` convention, and a pull request that must wait on another pull
request has nowhere structural to record it — that dependency belongs on the
issues the two PRs implement, where it also outlives both PRs being merged or
abandoned.

Three findings from the same probe change what gets built.

**A read cannot see the restriction, which promotes the verification step
below from good practice to necessary.** A `blocked_by` read against a pull
request answers `200` with an empty array — indistinguishable from an issue
that genuinely has no edges. Nothing in the read path ever says *wrong
kind of object*, so a skill that inspects relationships by reading them will
report a clean graph for a question the API declined to answer. Only the write
refuses, and only the write says so.

**The write surface is half what was assumed, which bounds the script.**
`POST .../dependencies/blocking` does not exist: `404` in GitHub's own error
shape, with `blocking` listed under reads only. So the first resident of
this skill's `scripts/` needs exactly one write route
(`POST .../dependencies/blocked_by`),
one `DELETE`, and two `GET`s. Four endpoints is small enough to make D3's
expiry note concrete — the script goes the day the MCP exposes them.

**The skill's two halves read through different clients, which is not an
incidental detail.** `closed_by_pull_requests` is absent from REST entirely;
the MCP is where it surfaces (GraphQL underneath, on the evidence of the field
name — unverified, since the container it was probed from serves only a pinned
set of GraphQL operations). REST offers `cross-referenced` on the issue
timeline instead, which renders the PR that closed an issue and a PR that
merely mentioned it *identically* — measured on `jmcvetta/career#177`, where
`#178` closed it and `#176` only refers to it. So the verification this section
already wants — *does the structured relationship match what the body claims?*
— asks the MCP for the closes-link and REST for the dependency edges. One
skill, two clients, for a reason that is neither arbitrary nor going away on
its own.

**The second client must be `curl`, not `gh api`** — measured in a web worker
on 2026-09-06, not assumed. `GITHUB_TOKEN` and `GH_TOKEN` are both present in
the environment, so a REST script authenticates fine on either surface; but
`gh` **is not installed on a web worker at all**. A script reaching for `gh api`
would work on the laptop, fail on the web, and thereby defeat the one thing this
whole plan exists to achieve.

This is the first place where D2's *"`gh` only for what MCP cannot do"* needs
sharpening. `gh` is not a fallback available everywhere — it is a
laptop-only convenience. Anything that must work on both surfaces has exactly
two clients open to it: the MCP, and `curl` against REST with the ambient
token. The constitution should say so in those terms, since the failure mode is
a script that passes every test on the machine where it was written.

Two design notes, both worth fixing before the skill is written.

**The graph is already being written to, badly.** The `pr` skill's
`Closes #123` convention is prose in a PR body, and that prose is exactly what
populates `closed_by_pull_requests`. So the relationship graph has a writer
today — an unvalidated string, with no way to notice when it is wrong. The skill
should treat the graph as the artifact and the text convention as one writer
into it, which also gives it a natural verification step: does the structured
relationship match what the body claims?

**Guard against manufactured relationships.** A skill whose description says
these relationships are wanted constantly will start inventing them, for exactly
the reason a role-framed security reviewer invents findings (Q5): an agent given
a job feels obliged to produce output. The firing moment is real and specific —
a dependency is discovered while planning work, or while writing a PR body and
realising it cannot merge first — and an inferred edge must pass an evidence
test before it is written: discovered in the work in hand, and evidenced by a
statement about the code rather than a shared subject. A wrong dependency is
worse than a missing one, because it blocks work silently and nobody thinks to
look for a relationship they did not create. That silence is what the skill
answers: it **writes the edge and reports the write**, both ends and the
evidence, rather than holding it for the user to confirm (#161).

## Migration inventory

### `dot-claude/commands/`

| Command | Disposition |
| ------- | ----------- |
| `save.md` | → memory skill; the compaction hook does the writing (D7), the skill stays manual |
| `restructure.md` | → memory skill (compaction half) + PR-to-plugin (constitutional half) |
| `opinion.md` | delete — fourth review verb |
| `quick-review.md` | delete — alias |
| `deep-review.md` | → `review` skill, depth inferred |
| `post-deep-review.md` | → folded into `review` / `pr-threads` |
| `godoc.md` | → skill, manual sweep |
| `copilot.md` | delete; protocol harvested into `pr-threads` |
| `dependabot.md` | → skill, fires on noticing open dependabot PRs (D11) |
| `haiku.md` | delete |

### `dot-claude/agents/`

`architecture-reviewer`, `logic-reviewer`, `planning-fitness-reviewer`,
`security-reviewer` → plugin `agents/`, pending the D6 panel audit. Model
pinning to be removed.

### `dot-claude/hooks/`

`block_chained_cd.sh` → delete (D1).

### `dot-claude/tools/`

`pr-review/` → an unknown number of surviving scripts, retired individually on
evidence (D3); at least two keep, probably three. `opencode-port/` is unrelated
to this work and stays put.

### `dot-claude/docs/`

`review-guidelines.md` → plugin, as a reference under the `review` skill.

### `dot-claude/CLAUDE.md`

Split across constitution, skills and references per the architecture above. Most of the 17KB is conditional — Cinc/InSpec,
Terraform, `gh` API recipes, pr-review tool docs — and currently pays rent in
every session for nothing.

### `dot-claude/settings.json`

Stays. Permissions, model, effort, editor mode and `autoMode` cannot move
(constraint 2), and should not.

## Risks

### R1 — The `SessionStart` hook is a single point of failure

Today a missing `CLAUDE.md` is visible; the file is right there. A hook that
exits non-zero — bad path, missing `${CLAUDE_PLUGIN_ROOT}`, plugin not enabled
in this repo — yields a session with no constitution at all, and the failure is
silent.

Mitigation: fail loudly, and test it. A pleasing recursion — the rule *code
without tests is broken* is carried by a shell script that must itself be
tested, or the rule silently ceases to exist. Cheap safety net: end the
constitution with a checkable token and provide a `verify` skill.

**That skill covers three of the four causes listed above and cannot cover the
fourth.** A skill ships *inside* the plugin, so in a repo where the plugin is
not enabled the `verify` skill is not there to be invoked either: the failure
disables its own detector. A bad path, a missing `${CLAUDE_PLUGIN_ROOT}` and a
non-zero exit are all answerable from inside, because the plugin loaded and the
hook merely misbehaved. "Not enabled here" has to be answered from outside —
`claude plugin list` on the CLI, or reading `.claude/settings.json` for the R4
stanza — and that check belongs to `bootstrap` (R4) plus one human-facing
habit: when a session feels unusually unconstrained, verify before assuming it
is being disobedient.

### R2 — RESOLVED: the constitution does not reach subagents, and a hook repairs it

Settled empirically on 2026-09-06 rather than left to the documentation, which
is silent. Method: a `SessionStart` hook injecting a nonsense passphrase, a
subagent asked for it, and the parent's `Agent` tool input inspected to confirm
the parent did not leak the answer into the subagent prompt.

| Delivery mechanism | Main session | Subagent |
| ------------------ | ------------ | -------- |
| `CLAUDE.md` | yes | **yes** |
| `SessionStart` `additionalContext` | yes | **no** |
| `SessionStart` + `PreToolUse` on `Agent` with `updatedInput` | yes | **yes** |

The middle row is the finding that matters: **a plugin-delivered constitution is
strictly weaker than the `CLAUDE.md` it replaces.** Delegation is central to the
workflow, so shipping the hook alone would have been a silent regression — the
worst kind of bug, invisible and only manifesting in the subagents doing the
actual work.

The third row is the repair, and it is verified rather than proposed. A
`PreToolUse` hook matching the `Agent` tool rewrites `tool_input.prompt` via
`hookSpecificOutput.updatedInput`, prepending the constitution. In the test the
prompt Claude *sent* contained no passphrase; the hook injected it in flight;
the subagent answered correctly.

This is the same house rule as everywhere else — *skill is the knowledge, hook
is the guarantee* — applied to the constitution itself.

**Consequence for the design, recorded as D12.** The constitution ships as one
file in the plugin with two injection points reading it:

1. `SessionStart` → `additionalContext`, for the main session.
2. `PreToolUse` on `Agent` → `updatedInput`, for every subagent.

One source of truth, two delivery paths, no drift. This supersedes the three
speculative mitigations previously listed here; agent-definition system prompts
and a "restate the rules when delegating" rule are both unnecessary now, the
first because it covered only custom agents and the second because it depended
on compliance rather than enforcement.

**Acceptance test, to be committed with the hook.** The experiment above *is*
the test, and it must ship as one: inject a known token, spawn a subagent, and
assert the token comes back. It covers R1 and R2 together — a constitution that
fails to load and a constitution that fails to propagate both show up as the
same red test. Given that the constitution carries the rule *code without tests
is broken*, it would be indefensible for its own delivery to be untested.

**But it cannot run in `make check`, and the split that follows is a better
test anyway.** Spawning a subagent needs a live model and therefore
credentials; this repository's CI is deliberately credential-free
(`permissions: contents: read`, and a `check` target reaching no further than
`claude plugin validate` and a manifest script). Adding a secret to CI to run
one test would trade that property away, so the test divides at the seam where
the credential requirement actually starts:

- **The credential-free half joins `make check`.** Run each hook script
  directly, feeding it synthetic event JSON on stdin, and assert on what it
  emits: `SessionStart` returns the token inside `additionalContext`, and the
  `Agent` `PreToolUse` hook returns an `updatedInput` whose prompt contains it.
  No model in the loop, and it catches every R1 cause — bad path, missing
  `${CLAUDE_PLUGIN_ROOT}`, malformed JSON, non-zero exit.
- **The live half runs on demand**, as a `claude plugin eval` case on the
  laptop or in a credentialed workflow. Only it can prove the harness
  *honours* `updatedInput`, which is the R2 finding proper. *(The harness has
  since changed — see [`0002`](../notes/0002-eval-harness.md); the live
  half is now `make evals-run TASKS='tasks/constitution/*.yaml'`. The split
  either side of the credential requirement is unaffected.)*

The division is honest rather than merely convenient: the first half tests this
plugin, the second tests an assumption about the harness that a future release
could withdraw without telling anyone. They fail for different reasons and
deserve to fail separately.

### R3 — Always-on context is a permanent tax, and D12 charges it twice

Every constitutional line is paid for in every session, forever — **and, under
D12, in every subagent that session spawns**, since the `PreToolUse` hook
prepends the whole constitution to each `Agent` prompt. The multiplier is not
one per session but one plus the number of subagents, and a workflow built
around delegation is precisely the one that pays it most often. The plan
encourages delegation, so the number grows.

This argues for the D12 repair, not against it: the alternative is subagents
that do not know the rules, which is the regression R2 exists to prevent. What
it does mean is that the admission filters were being calibrated against a cost
understated several-fold in any session that delegates. With no line limit
(deliberately), the three filters above — behaviour change in most sessions, a
nameable firing moment, and nothing the harness already says — are the only
thing holding the line, and each amendment has to apply them against the
multiplied cost rather than the per-session one. Another argument for
amendments being reviewable pull requests.

The cost is measurable rather than notional: `claude plugin details` reports a
plugin's projected token cost, which makes "what does this amendment cost"
a number a reviewer can ask for.

One mitigation, worth holding in reserve rather than building: the subagent
injection could carry a *reduced* constitution — identity and non-negotiables
without the skill index a subagent has less use for. That reintroduces exactly
the drift D12 exists to prevent, so it needs evidence that the full text is
actually hurting, not merely that it is large.

### R4 — Per-repo bootstrap friction

Plugin installation on web is per-project (constraint 7). Every new repo needs
the `extraKnownMarketplaces` / `enabledPlugins` stanza, and a repo that lacks it
silently runs without the constitution — the same failure mode as R1, from a
different direction.

**The obvious mitigation is circular, and seeing why decides where the stanza
really comes from.** A `bootstrap` skill ships inside the plugin, so in the one
situation that needs it — a repo whose missing stanza is why the plugin did not
load — the skill is not there to run. It can never bootstrap the repo it is
standing in.

What it can bootstrap is a *different* one, and that turns out to be the actual
workflow. The laptop has the plugin installed at user level, so a laptop
session carries the skill whatever repo is checked out; writing the stanza is a
laptop-side act, committed like any other file, and the web worker that clones
that repo later finds it already present. Three writers, in the order to reach
for them:

1. **A repo template** carrying `.claude/settings.json`, so new repos are never
   without it. Zero effort at the moment of creation, and the only one that
   scales.
2. **The `bootstrap` skill, run from the laptop** against a repo that predates
   the template. That is its whole job — retrofitting from outside, not
   self-repair from within.
3. **A copyable stanza in this repository's `README.md`.** The only route that
   survives a genuinely cold start, which is why it has to exist even though
   nobody will use it twice.

The cold start deserves stating plainly, because it is the case none of the
three fully covers: on a web worker, in a repo with no stanza and no laptop in
reach, the constitution is absent and nothing inside the plugin can say so.
Only R1's human-facing habit — check when a session feels unconstrained —
reaches it at all.

## Settled questions

Kept for the reasoning, since three of the four were resolved by finding the
answer already existed rather than by deciding anything.

- **Q1 — poetry in reviews: salutation or envoi?** Neither; both, already
  specified in `post-deep-review.md`, with the envoi conditional on approval.
  See D4.
- **Q2 — should `dependabot` be a Routine?** Bad premise: GitHub already runs
  that schedule. See D11.
- **Q3 — should `review` fire before every PR open?** No, definitively, and the
  reasoning generalises into a rule about which skills may self-trigger. See
  D10.
- **Q4 — how fat may the constitution get?** No limit, and the numbered "tiers"
  are renamed to named layers. See the architecture section.

## Open questions

### Q5 — Is the Opus judgment layer better as two roles or one?

Narrowed from "does the panel beat a single agent", which was the wrong
framing. The panel is already heterogeneous — Haiku for mechanical checks,
Sonnet for judgment, Opus for `security-reviewer` and `logic-reviewer`. The
Haiku tier is not competing with a strong reviewer; it is doing cheap
mechanical work and should stay regardless. **The live question is only whether
the two Opus reviewers are better as two roles or one.**

A panel is not free, and the costs are structural rather than incidental:

1. **Cross-cutting findings are invisible to it.** The most valuable finding in
   a review is often an interaction — this security fix breaks the retry path.
   The security reviewer sees the fix, the logic reviewer sees the retry path,
   neither sees the seam. A single agent holding the whole diff can. Panels are
   structurally blind to precisely the findings that matter most.
2. **Role framing manufactures findings.** An agent told it is the security
   reviewer will find security issues, because a security reviewer reporting
   nothing feels like a failed security reviewer. Single-agent review carries no
   such quota pressure.
3. **Synthesis is lossy.** The synthesiser sees findings, not the reasoning
   behind them, and dedupes, ranks, softens and drops accordingly.
4. **Volume dilutes.** A longer union gets skimmed, and the real bug sits at
   position 14. Precision matters more than recall for a review someone
   actually reads — the same argument that settled D10.
5. **The independence is weaker than it looks.** Four instances of one base
   model reading one diff have correlated errors: four draws from a single
   distribution, not four experts.

Against which the panel genuinely wins on recall for specialist dimensions
where a checklist beats a generalist's skim, and on diffs longer than one
attentive pass can hold.

The reason to measure is not that the panel is wrong. It is that:

> The panel was compensating for a weaker single reviewer. As the single agent
> gets stronger, the panel's marginal recall gain shrinks while its precision
> cost stays flat. **The crossover point moves.**

`deep-review.md` was designed on the far side of that crossover. Nobody has
checked whether it still is.

### Q6 — Which GitHub MCP toolsets? Measure, do not guess

Downgraded from a design question to a setup task, since the MCP has never been
run locally.

Setup has two paths: `github/github-mcp-server` locally via Docker or binary
with a PAT, or GitHub's hosted remote server — **verify whether the hosted one
requires a Copilot seat** before depending on it, as that subscription is
cancelled. The local path certainly does not.

On the toolset itself: enable everything, use it for a fortnight, then narrow to
what was actually called. Choosing a toolset now would be exactly the kind of
premature decision that produced ten commands nobody remembers.

## Sequencing

1. ~~**Settle R2** empirically.~~ **Done** — see R2. The answer requires a
   second hook, folded into **The constitution and its hooks** below.
2. **The constitution and its hooks.** Draft the constitution plus *both*
   delivery hooks — `SessionStart` for the main session, `PreToolUse` on
   `Agent` for subagents — and the acceptance test that proves the token
   reaches both.
3. ~~Split `pr` into `pr` / `pr-title` / `pr-body`; adopt MCP triggers (D2,
   D5).~~ **Done** — three sibling skills, triggering on
   `mcp__github__create_pull_request` and
   `mcp__github__update_pull_request`, with an eval suite each under `evals/`
   — written for `claude plugin eval` at the time, since ported to `coder_eval`
   per [`0002`](../notes/0002-eval-harness.md). `pr-threads` has since
   landed too; `pr-ci` remains.
4. Port `review` and the agent panel; audit for rot (D6).
5. Memory skill, written by the compaction hook (D7) — and the `PostCompact`
   `additionalContext` question answered first, since it decides whether the
   hook needs a nested Claude invocation at all.
6. Deletions (D1, D3, D4, D8), the `curl` rewrite of the surviving `gh`
   scripts (D3), and the repo template plus `bootstrap` skill (R4).
7. Trigger-accuracy suites across every skill. The three `pr*` skills, the
   constitution's live half and `review`'s depth routing have them; the rest do
   not. Written for `coder_eval`, not `claude plugin eval` — see
   [`0002`](../notes/0002-eval-harness.md) for why the harness changed.
