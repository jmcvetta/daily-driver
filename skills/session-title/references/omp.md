# Omp routes — session-title

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

One call: `daily_driver_set_session_title({ title })`. It takes the title
alone — the runtime adapter (`extensions/daily-driver.js`) applies it to the
current session, so there is no session id to look up first.

The title is plain text, never a serialized argument object. A direct tool call
passes it as the `title` field. The shell command surface takes one quoted
positional argument:

    daily_driver_set_session_title '#123 Short title'

The command's `-j`/`--json` argument is the only place a JSON argument object
belongs:

    daily_driver_set_session_title -j '{"title":"#123 Short title"}'

Passing that object as the positional argument sends the JSON text as the
title. The setter rejects a title that parses as a complete JSON object or
array, leaving the session name and title gate unchanged; braces or brackets
inside ordinary prose are not a JSON document and pass through.
For an explicit Omp embark request, these forms set the title:

```sh
daily_driver_set_session_title '⛵ EPIC #123 Short title'
daily_driver_set_session_title -j '{"title":"⛵ EPIC #123 Short title"}'
daily_driver_set_session_title --json '{"title":"⛵ EPIC #123 Short title"}'
daily_driver_set_session_title --help
daily_driver_set_session_title --help && daily_driver_set_session_title '⛵ EPIC #123 Short title'
```

Help output and a failed setter leave startup pending. The setter accepts
only a title matching the requested epic after its identity is confirmed.

The direct eval form is:

```js
await tool.daily_driver_set_session_title({title: '⛵ EPIC #123 Short title'});
```

For an explicit Omp embark request, the setter enforces the active epic's
title after a matching authoritative issue read. Read-only research remains
available while startup is pending; dispatch and claims remain blocked until
the active session name matches the epic form.

The runtime's own session-name limit is not measured here. The
thirty-character budget in `SKILL.md` applies whatever it is, because the cap
is this skill's rather than the tool's.
