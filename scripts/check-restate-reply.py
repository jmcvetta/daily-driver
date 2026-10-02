#!/usr/bin/env python3
"""The acceptance test for the `Stop` hook that asks for a concise restatement.

The real script is run as the harness runs it — synthetic event JSON on stdin —
and the answer is asserted on. No model is needed, so it belongs in `make
check` and in a CI that holds no credentials. Whether the restatement then
shortens anything is the eval comparison's question, not this file's.

No third-party imports.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOKS_JSON = ROOT / "hooks" / "hooks.json"
SCRIPT = ROOT / "hooks" / "restate-reply.py"
SEPARATOR = "──── Restated ────"


def run(stdin: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the hook as the harness does: argv, stdin, no plugin-root variable."""
    return subprocess.run(
        [str(SCRIPT), *args],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_ROOT"},
    )


def answer(message: str, active: bool = False) -> dict:
    """The hook's parsed answer for a `Stop` event carrying `message`."""
    event = {
        "hook_event_name": "Stop",
        "session_id": "check-restate-reply",
        "stop_hook_active": active,
        "last_assistant_message": message,
    }
    result = run(json.dumps(event))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class RestateReply(unittest.TestCase):
    def test_one_line_reply_blocks(self) -> None:
        """Without it a length threshold creeps back in and short replies are
        left unrestated, which is the arm this hook exists to measure."""
        self.assertEqual(answer("Done.").get("decision"), "block")

    def test_reason_names_the_reply_and_what_to_keep(self) -> None:
        """Without it a bare "restate concisely" passes: the model then
        describes its reply instead of giving it, or drops a risk."""
        reason = answer("Done.")["reason"]
        self.assertIn("the reply you just wrote", reason)
        for kept in ("fact", "uncertainty", "risk", "action"):
            self.assertIn(kept, reason)
        for dropped in ("preamble", "recap", "narration", "offers"):
            self.assertIn(dropped, reason)

    def test_reason_has_no_exemption(self) -> None:
        """Without it an exemption returns and the model calls every reply
        such a case and declines to restate (#458)."""
        reason = answer("Done.")["reason"].lower()
        for wording in ("document", "list", "stands as written", "stand as written"):
            self.assertNotIn(wording, reason)

    def test_reason_requires_the_separator_verbatim(self) -> None:
        """Without it the restatement arrives with no visible line between it
        and the draft, or with a paraphrase a transcript check cannot match."""
        self.assertIn(SEPARATOR, answer("Done.")["reason"])
        self.assertIn(SEPARATOR, SCRIPT.read_text(encoding="utf-8"))

    def test_active_stop_allows(self) -> None:
        """Without it the hook blocks its own restatement forever; the
        loop guard is the only thing that ends the turn."""
        self.assertEqual(answer("Done.", active=True), {})

    def test_missing_message_still_blocks(self) -> None:
        """Without it a reply the hook cannot read crashes the hook instead of
        asking for a restatement, or silently skips the turn."""
        result = run(json.dumps({"stop_hook_active": False}))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout).get("decision"), "block")

    def test_malformed_stdin_fails_loudly(self) -> None:
        """Without it garbage on stdin exits 0 with an empty answer, or exits 2,
        which on a Stop event blocks the stop and sends a spurious extra turn."""
        for stdin in ("", "not json", "[]", "null", '"hi"'):
            with self.subTest(stdin=stdin):
                result = run(stdin)
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout.strip(), "")

    def test_bad_argv_fails(self) -> None:
        """Without it a typo in hooks.json passes silently."""
        self.assertEqual(run("{}", "extra").returncode, 1)

    def test_script_is_executable(self) -> None:
        """Without it the hook command fails to launch and nothing is restated."""
        self.assertTrue(os.access(SCRIPT, os.X_OK))

    def test_docstring_records_the_separator(self) -> None:
        """Without it the separator the reason demands and the one the
        docstring documents drift apart."""
        doc = re.search(r'"""(.*?)"""', SCRIPT.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(doc)
        self.assertIn(SEPARATOR, doc.group(1))

    def test_wiring_is_stop_only(self) -> None:
        """Without it the hook is wired to the wrong event and never fires, or
        to SubagentStop, where it would restate a report the parent reads."""
        config = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))["hooks"]
        wired = {
            event: [
                h
                for entry in entries
                for h in entry.get("hooks", [])
                if SCRIPT.name in h.get("command", "")
            ]
            for event, entries in config.items()
        }
        self.assertEqual([e for e, hs in wired.items() if hs], ["Stop"])
        (handler,) = wired["Stop"]
        self.assertIn("${CLAUDE_PLUGIN_ROOT}", handler["command"])
        self.assertNotIn("SubagentStop", config)


if __name__ == "__main__":
    sys.exit(0 if unittest.main(exit=False).result.wasSuccessful() else 1)
