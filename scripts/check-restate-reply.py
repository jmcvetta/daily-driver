#!/usr/bin/env python3
"""The acceptance test for the `Stop` hook that judges a reply for unrequested content.

The hook is an agent-type hook in `hooks/hooks.json`: a small model reads the
user's last message from the transcript, compares the final reply with it,
and blocks the stop with a list of the sentences the message did not ask for.
The model call cannot run offline, so this file checks the wiring and the
contract the prompt states. Whether the restatement then removes anything is
the eval comparison's question, not this file's.

Why an agent hook and not a prompt hook: a prompt hook sees only the hook
input, and the `Stop` input carries the reply but not the user's message. An
agent hook can read `transcript_path`, which does.

No third-party imports.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SEPARATOR = "──── Restated ────"


def stop_handlers() -> list[dict]:
    """Every handler wired to the `Stop` event."""
    config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
    return [h for entry in config.get("Stop", []) for h in entry.get("hooks", [])]


def judge() -> dict:
    """The single agent-type `Stop` handler."""
    (handler,) = stop_handlers()
    return handler


class RestateReply(unittest.TestCase):
    def test_one_agent_handler_on_stop(self) -> None:
        """Without it a second Stop handler stacks a second restatement, or a
        command or prompt hook returns that cannot read the user's message."""
        self.assertEqual(judge()["type"], "agent")

    def test_not_wired_to_subagent_stop(self) -> None:
        """Without it the judge restates a subagent's report, which the parent
        reads and the user never does."""
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
        self.assertNotIn("SubagentStop", config)

    def test_prompt_receives_the_hook_input(self) -> None:
        """Without it the judge never sees the reply or the transcript path,
        and allows every stop."""
        self.assertIn("$ARGUMENTS", judge()["prompt"])

    def test_loop_guard(self) -> None:
        """Without it the judge blocks its own restatement and the turn never
        ends."""
        prompt = judge()["prompt"]
        self.assertIn("If stop_hook_active is true", prompt)
        self.assertIn('{"ok": true}', prompt)

    def test_reads_the_users_message_from_the_transcript(self) -> None:
        """Without it the judge cannot tell what was asked, and calls nothing
        unrequested, or everything."""
        prompt = judge()["prompt"]
        self.assertIn("transcript_path", prompt)
        self.assertIn("tool_result", prompt)
        self.assertIn("last_assistant_message", prompt)

    def test_block_names_the_sentences_and_the_separator(self) -> None:
        """Without it the block is a bare "restate concisely", which run 4 on
        #475 showed keeps the unrequested facts; or the restatement has no
        visible line between it and the draft."""
        prompt = judge()["prompt"]
        self.assertIn('"ok": false', prompt)
        self.assertIn("did not ask for", prompt)
        self.assertIn(SEPARATOR, prompt)

    def test_no_exemption(self) -> None:
        """Without it an exemption returns and the judge waves every list or
        document through, as the model did on #458."""
        prompt = judge()["prompt"].lower()
        for wording in ("document", "stands as written", "stand as written"):
            self.assertNotIn(wording, prompt)

    def test_timeout_is_bounded(self) -> None:
        """Without it a slow judge holds every reply for the harness's default."""
        self.assertLessEqual(judge()["timeout"], 60)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
