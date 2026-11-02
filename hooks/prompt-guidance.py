#!/usr/bin/env python3
"""Add response guidance to each submitted prompt unless it opts out."""

import json
import sys


def main() -> None:
    """Emit per-prompt style context without changing the submitted prompt."""
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return

    if not isinstance(event, dict):
        return
    prompt = event.get("prompt")
    if not isinstance(prompt, str) or prompt.rstrip().endswith("noterse"):
        return

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": "respond tersely in Simplified Technical English",
        }
    }))


if __name__ == "__main__":
    main()
