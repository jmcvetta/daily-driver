# Omp routes — provenance

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).


The block
=========

`daily_driver_get_session`, the tool `extensions/daily-driver.js` registers,
answers this session's own id (`ctx.sessionManager.getSessionId()`), its
name, the id of the model serving it, and the installed Omp version. Copy
`details.provenanceBlock` verbatim at the end of the body, including its
leading `---`. Do not run `omp --version`, reconstruct the block, or make a
confirmation read. Omp has no web URL for a session, so the id in the block
is bare rather than linked.

The version reader caches its result for the extension's lifetime. If no
version surface answers, the block records `Harness: Omp n/a`, never a
guessed version.


Commits
=======

Omp does not append a commit trailer of its own, so the agent adds
`Co-Authored-By: <model id> <address>` and, beside it, copies
`details.commitTrailer` from the same session read.

**No fixed address is documented.** Omp's own commit documentation ties a
co-author trailer to a configured session identity rather than to a built-in
default, and names no address for an unconfigured one. Inventing a domain to
complete the trailer would misattribute the commit to an address nobody
answers for, so where the session carries no configured identity of its own,
omit `Co-Authored-By` entirely and keep the session trailer alone. Where the
user has configured a commit identity through Omp's own settings, use it
verbatim rather than a value read from anywhere else.
