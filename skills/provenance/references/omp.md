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

For delegated review artifacts, `review-cycle` passes the path of the same
completed OCR JSON artifact as `reviewerOcrResult`. The wrapper reads only
`llm.model`, `llm.provider`, and `session_id` from that per-run file, uses
those values ahead of persistent configuration, and labels the model and
provider as requested/configured rather than verified backend-served identity.
Explicit `reviewerModel`, `reviewerProvider`, and `reviewerSession` remain
available for non-OCR callers; contradictory values fail before publication.
Unknown OCR fields remain `unreported`. Ordinary writes without reviewer
parameters keep their existing behavior.

Direct body-bearing `gh` calls from Bash are denied with a recovery instruction
that names `daily_driver_gh_write`. Read-only calls and non-body operations,
including labels and state changes, keep their existing `gh` routes. Callers do
not read session identity or `omp --version` and do not format provenance for
these writes.


Commits
=======

Omp does not append a commit trailer of its own, so the agent adds
`Co-Authored-By: <model id> <address>` and, beside it, a session trailer,
`Omp-Session: <id, or n/a>`.

**No fixed address is documented.** Omp's own commit documentation ties a
co-author trailer to a configured session identity rather than to a built-in
default, and names no address for an unconfigured one. Inventing a domain to
complete the trailer would misattribute the commit to an address nobody
answers for, so where the session carries no configured identity of its own,
omit `Co-Authored-By` entirely and keep the session trailer alone. Where the
user has configured a commit identity through Omp's own settings, use it
verbatim rather than a value read from anywhere else.
