#!/usr/bin/env python3
"""Ask for a concise restatement of an over-budget reply, once per turn.

A rule applied while generating does not shorten a reply. A restatement of a
draft that already exists does: the draft is in context and can be cut. So the
`Stop` hook lets the model write the draft, counts its lines the way the
constitution's *Before you reply* counts them, and where the draft is over the
budget blocks the stop with a reason that asks for the restatement. The draft
and the restatement are both visible in the transcript. Nothing is truncated or
rewritten here; the model writes the restatement and the hook only asks.

Contract, for the Claude Code `Stop` event:

- Input, on stdin as JSON: `last_assistant_message`, the full text of the
  final reply, and `stop_hook_active`, true when the turn is already
  continuing because a `Stop` hook blocked it.
- Output, on stdout: `{"decision": "block", "reason": <text>}` continues the
  turn with the reason shown to the model. `{}` lets the turn end.
- `stop_hook_active` true always allows the stop. That is the loop guard: one
  restatement per turn, never a restatement of the restatement.
- A reply is over budget when it has more than `BUDGET` lines. A line is a line
  as written; a bullet is one line; blank lines are not counted; a fenced code
  block is one line however long it is.
- Stdin that is not a JSON object exits 2 with nothing on stdout.

Wired to `Stop` only. A subagent's final message is its report to the parent,
and the parent's reply is what the user reads, so `SubagentStop` is not wired.
`scripts/check-restate-reply.py` is the acceptance test.

No third-party imports: this runs on a laptop, on a web worker, and out of a
test harness.
"""

from __future__ import annotations

import json
import re
import sys

# The constitution's budget: four lines, over which a reply is restated.
BUDGET = 4

_FENCE = re.compile(r"^\s*(```|~~~)")

# What the model is asked to do. It names the artifact, because a bare
# "restate concisely" made the agent describe its reply instead of giving it,
# and it names the two things the constitution puts outside the budget.
REASON = (
    "Restate the reply you just wrote — the one the user is about to read — "
    "in at most four lines, and send only that restatement. Keep every fact, "
    "uncertainty, risk and required action. Drop preamble, recap and detail "
    "the user did not ask for.\n\n"
    "Two kinds of reply sit outside the four-line budget: a document the user "
    "asked for, and a list the user will act on item by item. If your reply "
    "is one of those, it stands. Say so in one line and do not send a second "
    "copy of it."
)


def count_lines(text: str) -> int:
    """Lines of `text` as the constitution's budget counts them.

    Blank lines are not counted, a bullet is one line, and a fenced code block
    — fences and everything between — is one line, so short prose plus a
    command is not pushed over the budget by the command. An unclosed fence
    runs to the end of the text.
    """
    count = 0
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            if not in_fence:
                count += 1
            in_fence = not in_fence
        elif not in_fence and line.strip():
            count += 1
    return count


def decide(event: dict) -> dict:
    """The hook's answer for one `Stop` event: a block, or `{}` to allow."""
    if event.get("stop_hook_active") is True:
        return {}
    message = event.get("last_assistant_message")
    if not isinstance(message, str) or count_lines(message) <= BUDGET:
        return {}
    return {"decision": "block", "reason": REASON}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(f"usage: {argv[0].rsplit('/', 1)[-1]}", file=sys.stderr)
        return 2
    try:
        event = json.loads(sys.stdin.read())
    except json.JSONDecodeError as error:
        print(f"restate-reply: unparseable event JSON: {error}", file=sys.stderr)
        return 2
    if not isinstance(event, dict):
        print(
            f"restate-reply: event JSON is {type(event).__name__}, not an object",
            file=sys.stderr,
        )
        return 2
    json.dump(decide(event), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
