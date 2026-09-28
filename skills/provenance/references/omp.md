# Omp routes — provenance

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The block
=========

`daily_driver_get_session`, the tool `extensions/daily-driver.js` registers,
answers this session's own id (`ctx.sessionManager.getSessionId()`), its
name, and the id of the model serving it. Record both verbatim — `Model:
<model>` and `session: <id>` — with no note about where the values came
from. Omp has no web URL for a session, so the id goes in bare rather than
linked.

**The harness version** is `omp --version`, where it answers. A version no
surface in the session reports is `n/a`, never a guessed one.


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
