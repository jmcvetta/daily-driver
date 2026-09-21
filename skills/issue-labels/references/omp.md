# Omp routes — issue-labels

`SKILL.md` names each operation in words. This file names the call, for a
session running in Oh My Pi. Claude Code's routes are in
[`claude.md`](claude.md), Codex's in [`codex.md`](codex.md).

Two clients share the work, as they do for `undertake`: the built-in `github`
tool reads what it covers, `gh` writes, and `issue://<number>` resolves a read
from the same cache the `github` tool writes to.


Reading and writing a label
===========================

| Operation | Call |
| --------- | ---- |
| Read the labels on one issue | `issue://<number>`, or `gh issue view <number> --json labels` |
| Label an issue being opened | `gh issue create --label task` |
| Label an issue that exists | `gh issue edit <number> --add-label task` |
| Take a label off | `gh issue edit <number> --remove-label proposal` |

**`--add-label` adds; it does not replace.** That is the opposite of the
Claude route, and it is the safer half: nothing else on the issue is lost —
no read-first is needed here.

It is also the half that breaks the exactly-one invariant. Swapping one
standard label for another takes both flags — `--add-label task
--remove-label proposal` — and an `--add-label` on its own leaves the issue
carrying two of the six, which `SKILL.md` makes a stop. Write the swap as
one call with both flags rather than as two calls with one each.

Reconciling the story marker
============================

`issue-deps` supplies a verified direct-parent read. If its parent has the
`epic` label, use `gh issue edit <number> --add-label story`. If no parent is
confirmed or its labels omit `epic`, use `gh issue edit <number> --remove-label
story`. A failed graph read preserves the current labels and reports the
limitation. These additive writes preserve the issue kind,
stock labels, bot labels, and unrelated labels.

Finding the issues that carry a label is `gh issue list --label task`, or
`github.search_issues` with `label:task` in the query.
