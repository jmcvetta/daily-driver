# Omp routes — provenance

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The block
=========

Every body-bearing Omp GitHub write uses `daily_driver_gh_write` with `args`
as an array of `gh` arguments, excluding the executable. The tool runs `gh`
directly without shell interpolation and adds the provenance block immediately
before the write. It reads the live model, provider and session id from the
execution context on each call; it reads and caches the installed Omp version
once per extension instance, using `n/a` when unavailable.

The serving provider is the harness-reported one,
`ctx.models.current()?.provider ?? ctx.model.provider`, the same selection
`extensions/undertaking-routing.mjs` uses. Never derive it from the model id.
Where neither surface reports a provider, the block carries `Provider: n/a`.

For `--body` and `--body-file`, the wrapper appends the block while retaining
one complete block per distinct `(Model, Provider, Harness, Session)` tuple in
original order. It removes exact duplicate blocks, preserves incomplete
historical records and all other body content, and does not modify the
caller's body file. A historical block with no `Provider:` line compares as
provider `n/a`, and the two session-field capitalizations are the same field.
For supported `gh api --input` review and reply routes, it updates the JSON
`body` fields, including each inline review comment, in a private temporary
copy and removes that copy after success or failure.

For delegated review artifacts, callers may pass observed reviewer identity
as `reviewerModel`, `reviewerProvider`, and `reviewerSession`. The wrapper
labels that reviewer record separately from publisher provenance; unknown
reviewer fields are `unreported`. Ordinary writes without `reviewerModel`
keep their existing behavior. Do not infer reviewer identity from the publisher.

Direct body-bearing `gh` calls from Bash are denied with a recovery instruction
that names `daily_driver_gh_write`. Read-only calls and non-body operations,
including labels and state changes, keep their existing `gh` routes. Callers do
not read session identity or `omp --version` and do not format provenance for
these writes.


Commits
=======

Omp does not append commit trailers itself. Prepare each agent-authored commit
with `daily_driver_commit_message` before using Omp's native selective commit:

```js
const result = await tool.daily_driver_commit_message({ body: substantiveBody });
const preparedBody = result.details.body;
const draft = await commit.draft({ repo: taskWorktree });
await draft.commit(subject, { body: preparedBody });
```

The tool prepares text only; it does not stage, commit, push, merge, or change
configuration. Its structured `details` contains `body` and `trailers` (an
array of `{ key, value }` records). It reads the live session on every call and
adds `Omp-Session: <id>` or `Omp-Session: n/a` when unavailable. It preserves
unrelated trailers and deduplicates attribution records by case-insensitive
key and exact value. Only actual trailing Git trailers count, not quoted
examples or Markdown provenance blocks.

**No fixed address is documented.** Pass `coAuthor` only when an Omp
configured commit identity is positively verified from a documented readable
harness surface; pass its value verbatim. The installed harness may expose no
such surface. In that case omit `coAuthor`, report the limitation, and retain
the session trailer alone. Never infer an address from Git author settings,
model or provider names, or historical commits, and never change configuration
to obtain one. Invalid or multiline values fail preparation.

For an amendment, prepare the existing commit body again, preserving its
substantive content and trailers; the tool does not accumulate duplicate
attribution. Use native `draft.commit` with `amend: true` only when its
documented amendment conditions hold. For an in-progress mechanical
conflict-resolution merge, native selective commits refuse the operation: use
the narrow plain-Git completion route in
[`pr`'s Omp reference](../../pr/references/omp.md#the-owner-continuation),
passing the prepared message and retaining hooks and signing.

For a squash, pass source commit messages in `sourceMessages`; distinct
`Co-Authored-By`, `Omp-Session`, `Claude-Session`, and `Codex-Session` trailers
are retained in source order alongside the landing session. Missing attribution
is not fabricated. [`embark`'s Omp reference](../../embark/references/omp.md#the-watch)
defines the gated, paginated landing route. GitHub's server-authored
update-branch commits do not accept a custom message; this route cannot add
trailers to them. Claude Code and Codex retain their own best-effort contracts
and must not duplicate trailers their harness supplies.
