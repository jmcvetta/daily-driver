# Codex routes — session-title

`SKILL.md` names each operation in words. This file names the call, for a
session running in Codex. Claude Code's routes are in
[`claude.md`](claude.md), Omp's in [`omp.md`](omp.md).

One call, where the session is offered it: **`set_thread_title`**, in the
`agent_tasks` tool namespace — *"Rename a Codex task. Omit `threadId` to
rename the calling task."* Omitting `threadId` is what makes it the one call
rather than two: it takes the title alone, which is Omp's shape and not Claude
Code's, and there is no session id to look up first.

The title itself is `SKILL.md`'s, budget included. The forty characters are
this skill's cap rather than any tool's, so they hold here whatever Codex's own
limit turns out to be.


Where it is not offered
=======================

`agent_tasks` is a **dynamic tool namespace of the terminal UI**, served only
where that UI is attached to a running app-server daemon. It is not in the tool
list of a `codex exec` run, and an unattended run is a `codex exec` run.

So the common case on this harness is the stop `SKILL.md` already states under
`Setting it`: **no surface, so say so in a line and stop.** Read the session's
own tool list rather than assuming either way — the namespace is either offered
or it is not, and that is a cheap thing to look at.

**There is no shell fallback, and it is worth knowing that there is none.**
`codex` addresses a saved session by id *or by name* in four subcommands —
`queue --thread`, `archive`, `delete`, `resume` — so a reader reasonably
expects a fifth that sets the name. There is not one. The terminal UI's `/name`
renames the current thread, and a keystroke a person types is not a route a
session can take.


What the name is read in
========================

Not a phone list. On this harness the name is what `codex resume`'s picker
lists, and what `--thread`, `archive` and `delete` accept in place of a UUID.
That second use is the one worth writing for: a name is an **address** here,
and `#{number} {shortened issue title}` is already the form that makes one
session distinguishable from a dozen siblings started the same afternoon.

An address has two traps a label does not, and both are the reader's to carry
because the form does not solve either:

- **The form is not unique.** Two sessions on one issue title to the same
  string, and that string is what a destructive subcommand takes. Address a
  session by its UUID wherever the operation is one that cannot be undone, and
  keep the name for reading.
- **It starts with `#`.** Unquoted in a shell, the whole argument is a comment
  and the subcommand is called with none. Quote it.


Provenance
==========

`codex-cli 0.154.0`, read on 2026-09-12 from the installed binary and from
`codex --help` and its subcommands. The subcommand surface is quoted from
`--help` output. **`set_thread_title` was not driven**: reaching it needs the
terminal UI, which [#181](https://github.com/jmcvetta/daily-driver/issues/181)
established cannot be reached without credentials. The tool name and its
description are read from the binary's own tool table, beside the eight other
`agent_tasks` tools [`../../embark/references/codex.md`](../../embark/references/codex.md)
lists.
