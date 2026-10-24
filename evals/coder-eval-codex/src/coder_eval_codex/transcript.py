"""The turn transcript the judge reads, rendered — with no `coder_eval` in sight.

Everything in this module is pure: a string in, a string out. That is
deliberate, and it is the same split `coder_eval_omp/rpc.py` makes. The agent in
`agent.py` cannot be exercised without a `coder_eval` install and the Codex SDK,
so anything load-bearing that lives there is untested code. What is load-bearing
is here instead.

One thing it owns, and it is a silent zero if it is wrong.

**The reply the judge reads.** Every judge rubric under `evals/tasks/` anchors
on the `[RESULT - …]` tag that `coder_eval`'s `format_messages` emits, and
scores 0.0 where the tag is missing — by design, so a drifted harness cannot
report a plausible number. `coder_eval` builds that transcript for its Claude
Code agent only; its Codex agent hands the judge `result_text`, the assistant
message deltas joined and nothing else. A Codex arm that did the same would
score every judged row 0.0, which is most of the `references` suites and both
halves of the constitution suite.

**What this module does NOT own, and why there is only one normalisation here
rather than the two the Omp arm needed.** A skill engagement is already visible
to `coder_eval`'s `skill_triggered` on Codex. That criterion matches
`skills/<name>/` in any string tool parameter and its own docstring names Codex
as the agent it was added for; `CodexAgent._setup_skills` links each plugin
root's skills into `<cwd>/.agents/skills/<name>/`, the Codex SDK types
`CommandExecutionThreadItem.command` as `str`, and `_extract_command_telemetry`
puts that string in `parameters["command"]`. So the path the model reads carries
the substring the criterion looks for, with nothing to rename. Issue #185 was
written expecting `skill://<name>` here, the spelling Omp uses; the spike in
#181 measured that Codex does not use it — the model reads `SKILL.md` itself and
`skill://` passes through as literal text.
"""

from __future__ import annotations

import re


#: What `format_messages` renders an empty turn as. A judge must see the same
#: thing on both harnesses, including when there is nothing to see.
EMPTY_OUTPUT = "[No output]"

#: The tag every rubric here anchors on, as `format_messages` writes it. Matched
#: at a line start, with the two statuses that function can emit.
RESULT_TAG = re.compile(r"^\[RESULT - (?:SUCCESS|ERROR)\]", re.MULTILINE)

#: How `format_messages` opens an assistant block.
ASSISTANT_TAG = "[ASSISTANT] "


def is_already_tagged(text: str) -> bool:
    """Is `text` already a `format_messages` transcript rather than bare reply text?

    Both halves are required: the transcript opens with an `[ASSISTANT] ` block
    and carries a `[RESULT - …]` line. Requiring both is what keeps a reply that
    merely quotes the tag from being mistaken for a rendered transcript — such a
    reply is re-rendered, so the judge anchors on the tag this module wrote
    rather than on one the model typed.

    It exists for one case: a future `coder_eval` that starts tagging its Codex
    agent's output. Re-rendering that would nest the whole transcript inside a
    second result block, and the judge would read the narration as the reply.
    """
    return text.startswith(ASSISTANT_TAG) and RESULT_TAG.search(text) is not None


def render_agent_output(text: str, *, is_error: bool = False) -> str:
    """Bare Codex turn text, in the shape every judge rubric here anchors on.

    `coder_eval`'s `format_messages` renders a Claude turn as `[ASSISTANT] …`
    blocks followed by one `[RESULT - …]` carrying the reply, so the reply
    appears twice. `CodexAgent` has one block to render — `result_text`, the
    turn's assistant deltas joined — and this emits that same shape for it, byte
    for byte with what `coder_eval_omp.rpc.render_agent_output` emits for a
    single block, which keeps one rubric readable across harnesses without
    either package depending on the other.
    harnesses without either package depending on the other.

    An empty turn renders `EMPTY_OUTPUT`, and an already-rendered transcript is
    returned unchanged.
    """
    if is_already_tagged(text):
        return text
    if not text or not text.strip():
        return EMPTY_OUTPUT
    status = "ERROR" if is_error else "SUCCESS"
    # The text is written through unstripped, because the Omp renderer writes
    # its blocks through unstripped and the two must agree byte for byte.
    return f"{ASSISTANT_TAG}{text}\n[RESULT - {status}] {text}"
