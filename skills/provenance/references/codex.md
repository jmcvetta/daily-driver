# Codex routes — provenance

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in [`claude.md`](claude.md),
Oh My Pi's in [`omp.md`](omp.md).


The block
=========

Codex exposes no session id, so record `session: n/a` — the marker
`SKILL.md` prescribes, not a diagnostic about the missing surface. The
`Model:` line repeats what the harness states is serving the turn — the
session's configured model — rather than a recalled name.

**The harness version** is `codex --version`, where it answers. A version no
surface in the session reports is `n/a`, never a guessed one.


Commits
=======

Codex documents a default commit trailer of its own, gated behind its
`codex_git_commit` feature and set by the `commit_attribution` key in
`config.toml`: `Co-authored-by: Codex <noreply@openai.com>`, disabled by an
empty value, or replaced by whatever string the user has set there. The
address names Codex's own bot identity rather than the concrete model
serving the turn, because that is the identity the address is documented to
resolve to — substituting a model id in its place would produce a trailer
GitHub cannot attribute to anything.

**Where that feature is enabled, Codex appends the trailer itself and the
agent adds nothing.** Where it is disabled or the session cannot tell, add
the same default by hand, `Co-Authored-By: Codex <noreply@openai.com>`,
unless the user's own `config.toml` sets a different `commit_attribution`
value — then use that value verbatim. Add a session trailer beside it,
`Codex-Session: n/a`, since Codex exposes no session id to fill it with.
