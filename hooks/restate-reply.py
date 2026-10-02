#!/usr/bin/env python3
"""Ask for a concise restatement of every final reply, once per turn.

A rule applied while generating does not shorten a reply. A restatement of a
draft that already exists does: the draft is in context and can be cut. So the
`Stop` hook lets the model write the draft, then blocks the stop with a reason
that asks for the restatement. The draft and the restatement are both visible.
Nothing is truncated or rewritten here; the model writes the restatement and
the hook only asks.

Contract, for the Claude Code `Stop` event:

- Input, on stdin as JSON: `last_assistant_message`, the full text of the
  final reply, and `stop_hook_active`, true when the turn is already
  continuing because a `Stop` hook blocked it.
- Output, on stdout: `{"decision": "block", "reason": <text>}` continues the
  turn with the reason shown to the model. `{}` lets the turn end.
- `stop_hook_active` true always allows the stop. That is the loop guard: one
  restatement per turn, never a restatement of the restatement.
- There is no length threshold. Every final reply is restated, including a
  one-line one, and the reason names no case in which the draft may stand.
  Whether short replies are harmed is a question for the eval comparison.
- Stdin that is not a JSON object, or an unexpected argument, exits 1 with
  nothing on stdout. Not 2: on a `Stop` event exit 2 blocks the stop and feeds
  stderr to the model, so a bad payload would cost a spurious extra turn
  instead of surfacing as a hook error.

The separator is `SEPARATOR` below, `──── Restated ────`. The restatement must
open with that line, verbatim, so the user can see where the draft ends.

Which barrier, and why: the `Stop` output contract offers `systemMessage`, a
field the harness renders to the user. It is not used. It is shown as a hook
notice, not as part of the assistant's reply, so it need not sit between the
draft and the restatement, and it is absent from the transcript the eval
harness captures, so the comparison could not check it. A line the model writes
is in the reply, in order, in every transcript. The cost: the model can omit
it. `scripts/check-restate-reply.py` checks that the reason requires it; the
eval transcripts show whether the model complies.

Wired to `Stop` only. A subagent's final message is its report to the parent,
and the parent's reply is what the user reads, so `SubagentStop` is not wired.
`scripts/check-restate-reply.py` is the acceptance test.

No third-party imports: this runs on a laptop, on a web worker, and out of a
test harness.
"""

from __future__ import annotations

import json
import sys

# The visible barrier between the draft and the restatement.
SEPARATOR = "──── Restated ────"

# What the model is asked to do. It names the artifact, because a bare
# "restate concisely" made the agent describe its reply instead of giving it.
# It names no case in which the draft may stand: measured on #458, a stated
# exemption let the model decline every restatement. It does not ask for the
# shortest possible text: measured on #485, "as concisely as you can" made the
# model answer "Nothing new to report" where the question needed a fact, so the
# reason demands the specific answer and names what to cut instead.
REASON = (
    "Restate the reply you just wrote — the one the user is about to read — "
    "so that it answers the user's last message directly, and send only that "
    "restatement. Open it with this line, exactly as written, on a line of "
    f"its own: {SEPARATOR}\n\n"
    "State the specific answer itself — the facts, names and numbers the user "
    "needs — never a pointer to an earlier reply. Keep every fact, "
    "uncertainty, risk and required action the answer needs. Cut preamble, recap, narration, offers and detail the user "
    "did not ask for."
)


def decide(event: dict) -> dict:
    """The hook's answer for one `Stop` event: a block, or `{}` to allow."""
    if event.get("stop_hook_active") is True:
        return {}
    return {"decision": "block", "reason": REASON}


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(f"usage: {argv[0].rsplit('/', 1)[-1]}", file=sys.stderr)
        return 1
    try:
        event = json.loads(sys.stdin.read())
    except json.JSONDecodeError as error:
        print(f"restate-reply: unparseable event JSON: {error}", file=sys.stderr)
        return 1
    if not isinstance(event, dict):
        print(
            f"restate-reply: event JSON is {type(event).__name__}, not an object",
            file=sys.stderr,
        )
        return 1
    json.dump(decide(event), sys.stdout)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
