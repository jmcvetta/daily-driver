"""A row's tool lists, turned into the `omp` flag that enforces them.

Pure, for the reason `rpc.py` is: `scripts/check-omp-agent.py` runs it in
`make check` with no `coder_eval` and no `omp` installed.

Omp's `--tools=<list>` names the built-in tools a session gets, and works with
`--mode rpc`. A row writes its lists in Claude Code's vocabulary, so this
module maps them across. It fails closed: a list it cannot express raises, and
the task fails rather than running with every tool on.

What `--tools` does and does not restrict, measured on Omp 18.4.10:

- It filters Omp's built-in tools only. Tools a plugin's extension registers
  stay on whatever the list says, `--no-tools` included.
- With `read` on, Omp adds a `write` tool that dispatches `xd://` devices and
  rejects every other path. It writes no file.
- `read` still opens URLs and Omp's `pr://` and `issue://` GitHub schemes.

`launch.py` and `eval_guard.js` close the last two; the first stays open on
purpose. `docs/notes/0013-the-omp-arm.md` records why.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


#: Claude Code tool name -> the Omp built-in tool that does the same job, or
#: None where Omp has no counterpart. Omp's names are from its own
#: `--tools=<unknown>` error listing. `Skill` maps to `read` because Omp
#: engages a skill by reading `skill://<name>`; `rpc.py` maps that read back.
OMP_TOOL_FOR: dict[str, str | None] = {
    "Read": "read",
    "Grep": "grep",
    "Glob": "glob",
    "Bash": "bash",
    "Write": "write",
    "Edit": "edit",
    "Task": "task",
    "Agent": "task",
    "WebSearch": "web_search",
    "Skill": "read",
    "NotebookEdit": None,
    "WebFetch": None,
}

# The Claude Code tools a row gets when it names no `allowed_tools`: every
# tool with an Omp twin. Omp-only built-ins (`github`, `eval`, `debug`, `lsp`,
# the memory tools and the rest) have no place here, so a row never gets them.
_CLAUDE_CODE_DEFAULTS: tuple[str, ...] = tuple(name for name, tool in OMP_TOOL_FOR.items() if tool is not None)


class UnenforceableToolList(ValueError):
    """A row's tool list names a tool this arm cannot grant or cannot recognize."""


@dataclass(frozen=True)
class ToolSelection:
    """The Omp tools a row gets, and the flag that grants exactly those."""

    tools: tuple[str, ...]
    """Omp built-in tool names, in the order the row implies."""

    read_for_skill: bool
    """`read` is on only because the row allows `Skill`, not `Read`."""

    webfetch_via_read: bool
    """The row denies `WebFetch` while `read` is on.

    `read` opens URLs unless `fetch.enabled` is off, which `launch.OMP_CONFIG`
    sets for every row, so this no longer marks an open path.
    """

    @property
    def argv(self) -> tuple[str, ...]:
        """The `omp` command-line flag: `--tools=<list>`, or `--no-tools`."""
        if not self.tools:
            return ("--no-tools",)
        return (f"--tools={','.join(self.tools)}",)


def select_tools(allowed: Sequence[str] | None, disallowed: Sequence[str] | None) -> ToolSelection:
    """Map a row's `allowed_tools` and `disallowed_tools` to Omp's tool set.

    `allowed` set (even empty) is the whole grant. Unset, the grant is Claude
    Code's default tools. `disallowed` is then removed from the grant.

    One exception: an allowed `Skill` keeps `read` on, because `read` is how
    Omp engages a skill. `read_for_skill` reports when that happens.

    Raises `UnenforceableToolList` for an allowed tool with no Omp counterpart,
    and for any name not in `OMP_TOOL_FOR`, so that a typo cannot leave a tool
    on that the row meant to remove.
    """
    unknown = [name for name in (*(allowed or ()), *(disallowed or ())) if name not in OMP_TOOL_FOR]
    if unknown:
        raise UnenforceableToolList(
            f"omp: tool name(s) {', '.join(map(repr, unknown))} have no entry in the Omp tool map, "
            "so the row's tool list cannot be enforced"
        )
    if allowed is not None:
        unmapped = [name for name in allowed if OMP_TOOL_FOR[name] is None]
        if unmapped:
            raise UnenforceableToolList(
                f"omp: allowed tool(s) {', '.join(map(repr, unmapped))} have no Omp counterpart, "
                "so the row cannot run as written on this arm"
            )

    denied = set(disallowed or ())
    granted = [name for name in (_CLAUDE_CODE_DEFAULTS if allowed is None else allowed) if name not in denied]
    # A denied `Skill` takes nothing away: `read` belongs to `Read` as well.
    denied_omp = {OMP_TOOL_FOR[name] for name in denied if name != "Skill"}

    tools: list[str] = []
    for name in granted:
        tool = OMP_TOOL_FOR[name]
        if tool is None or (name != "Skill" and tool in denied_omp):
            continue
        if tool not in tools:
            tools.append(tool)
    return ToolSelection(
        tools=tuple(tools),
        read_for_skill="Skill" in granted and "Read" not in granted,
        webfetch_via_read="WebFetch" in denied and "read" in tools,
    )
