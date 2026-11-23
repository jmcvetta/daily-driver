"""What the Codex CLI says about itself, parsed without importing coder_eval.

``start()`` records the binary's version, authentication mode and model catalog
before any inference. These parsers are pure so a test can pin the fail-closed
behaviour without an authenticated CLI:

* an unrecognized login sentence is ``unknown``, never optimistically treated as
  the subscription;
* a catalog that cannot be parsed is empty, so the caller records "unchecked"
  instead of inventing a model list.
"""

from __future__ import annotations

import json


def classify_auth(status: str) -> str:
    """Classify ``codex login status`` output: subscription, api_key, none or unknown.

    Tolerant because the CLI may reword the sentence; every unrecognized
    non-empty answer is ``unknown`` and the caller fails closed.
    """
    text = status.strip().lower()
    if not text:
        return "unknown"
    if "not logged in" in text or "no credentials" in text:
        return "none"
    if "api key" in text or "api_key" in text:
        return "api_key"
    if "chatgpt" in text or "subscription" in text:
        return "subscription"
    return "unknown"


def model_slugs(stdout: str) -> list[str]:
    """The model ids in ``codex debug models`` JSON, or an empty list.

    An unreadable answer is empty on purpose: the caller records that the
    catalog was not checked rather than treating a parse failure as proof the
    requested model is unavailable.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    entries = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        return []
    return [str(entry["slug"]) for entry in entries if isinstance(entry, dict) and entry.get("slug")]
