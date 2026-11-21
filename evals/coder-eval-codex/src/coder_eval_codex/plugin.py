"""The entry point `coder_eval` calls to learn about the `codex-daily-driver` kind.

`coder_eval` scans every installed distribution for an entry point in the
`coder_eval.plugins` group and calls its target with the agent registry. Its own
built-in agents register through that same group, so the seam cannot silently
rot.

Registration is deliberately here rather than as a decorator on the agent class:
the registry rejects two plugins claiming one kind, and a decorator would claim
the kind on any import of the module, including one from a tool that only wanted
to read it.
"""

from __future__ import annotations

from typing import Any

from .agent import AGENT_KIND, CodexCLIAgent, CodexCLIAgentConfig


def register(registry: Any) -> None:
    """Bind `codex-daily-driver` to its CLI driver and config class.

    Idempotent: re-registering the same pair is allowed by the registry, which
    rejects only a second plugin trying to shadow the kind with a different
    implementation.
    """
    registry.register(AGENT_KIND, CodexCLIAgentConfig)(CodexCLIAgent)
