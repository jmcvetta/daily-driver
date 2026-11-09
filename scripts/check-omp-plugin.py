#!/usr/bin/env python3
"""Prove that Omp actually loads this plugin, by asking Omp.

`check-omp-extension.mjs` drives `extensions/daily-driver.js` under Node with a
faked `ExtensionAPI`. That proves the adapter's logic and nothing about
discovery: it never starts Omp, so a plugin whose skills Omp does not find, or
whose extension Omp never reaches, passes it green.

This is the other half. It starts a real `omp --mode rpc` twice, once per route
a person takes, and asks the running agent what it got.

THE TWO ROUTES, AND WHY BOTH ARE HERE

    `omp --plugin-dir <path>` is the local-development route. It builds a
    synthetic plugin root and runs it through discovery, so the skills are
    found. It does *not* load the extension: extension entry points come from
    `omp.extensions` in an *installed* plugin's manifest, and a `--plugin-dir`
    root is never installed. Measured, on omp 18.1.17.
    `omp plugin link <path>` is the install route, and the one a marketplace
    install produces: a symlink under `~/.omp/plugins/node_modules` and an
    entry in the lockfile. The extension loads on this route and only on it.

    A check that took either route alone would miss half the plugin, so it
    takes both.

WHAT IT ASSERTS

    On both plugin routes, every published skill is offered as a
    `skill:<name>` command. The expected set comes from `skills/`, not a
    hard-coded list.
    From this repository, the local maintenance skill is discovered and its
    repository-local body is readable. From an unrelated project, both plugin
    routes expose the published skills but not that local command.
    On the linked route, `omp plugin list` reports `daily-driver` enabled.
    On the linked route, the extension loads. Omp reports a module that throws
    on import by printing `Failed to load extension` and carrying on, so the
    assertion is on that line's absence -- measured against a module made to
    throw, rather than assumed.
    On both routes, no `extension_error` frame. That frame carries a *runtime*
    error from an extension handler, which is a different failure from a
    module that will not import, and neither one fails anything else.
    Omp exits 0 when stdin closes.

WHAT IT DOES NOT ASSERT

    That a skill fires, or that its body is read. That is a behavioural
    question and it needs a model; `evals/` is where it is asked.
    That the *marketplace* install works -- `omp plugin marketplace add`
    followed by `omp plugin install` reaches the network and writes a real
    `~/.omp`. `omp plugin link` exercises the same installed-plugin code path
    offline and against a throwaway `HOME`; the README documents the
    marketplace commands and a person runs them.

WHY IT NEEDS NO CREDENTIALS

    `get_available_commands` is answered from the session's own command
    registry. No model is called and the run costs nothing. Omp does insist on
    a model being *available* before it starts a session, so the throwaway
    `HOME` carries a placeholder one pointing at a closed port -- see
    `isolated_environment`, which also says why the child's environment is
    built rather than inherited. `HOME` is throwaway for the length of the run,
    so the laptop's own skills, providers and installed plugins cannot make
    this pass -- or fail -- on their own, and `omp plugin link` writes inside
    it.

Omp on `PATH` is the one thing it does need, and it is why `make
check-omp-plugin` sits outside `make check` rather than inside it -- a laptop
editing a skill must not start needing a second harness. CI's `omp` job runs
it, gated on the files that can actually break the integration; that job's
comment lists them and says why each is there.

No third-party imports, for the reason `check-manifests.py` gives: a
dependency install between the laptop and CI is a place for them to differ.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The plugin name the manifests carry. `check-manifests.py` asserts the three
# manifests agree on it, so naming it once here is not a fourth copy to drift.
PLUGIN_NAME = "daily-driver"

# Generous, because it covers a cold start of a runtime that walks the
# filesystem for skills, and because the cost of a timeout that is too short is
# a red build nobody can reproduce. Nothing here waits on a model.
TIMEOUT_SECONDS = 180.0

# The one command each run asks for, and the id it is correlated by. Omp echoes
# the id on the response, which is how the response is told from the events and
# `available_commands_update` frames arriving around it.
REQUEST_ID = "check-omp-plugin-1"
REQUEST = {"id": REQUEST_ID, "type": "get_available_commands"}

# What Omp prints when an extension module will not import. It does not raise,
# it does not exit non-zero, and it emits no frame -- the session simply runs
# without the extension, which is the silent failure this line is the only
# report of.
LOAD_FAILURE = "Failed to load extension"


class CheckFailed(Exception):
    """A failed assertion, with the stderr that explains it."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def expected_skill_commands() -> list[str]:
    """The `skill:<name>` command for every skill in the tree.

    `check-manifests.py` already asserts that a skill's frontmatter `name`
    matches its directory, so the directory name is the skill name and reading
    it here does not duplicate that check.
    """
    return sorted(f"skill:{d.name}" for d in (ROOT / "skills").iterdir() if (d / "SKILL.md").is_file())


def isolated_environment(home: Path) -> dict[str, str]:
    """A throwaway `HOME` and a built environment, not an inherited one.

    Two files go in it. `config.yml` turns skill commands on, which are off by
    default -- without them `get_available_commands` returns the builtins and
    nothing else, a pass that would mean nothing. `models.yml` declares one
    placeholder model, because Omp refuses to start a session with no model
    available at all: it points at a closed port and carries `auth: none`, so
    it satisfies the startup check while being unusable, and nothing in this
    run ever calls a model anyway.

    The environment is built from a short allow-list rather than copied from
    the caller's. A copied environment carries the machine's provider
    credentials -- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, and the rest --
    and those are exactly what decides whether Omp finds a model. Inherit them
    and this check passes on a laptop for a reason CI does not have, which is
    the failure that wrote this paragraph.
    """
    agent = home / ".omp" / "agent"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "config.yml").write_text("skills:\n  enableSkillCommands: true\n", encoding="utf-8")
    (agent / "models.yml").write_text(
        "providers:\n"
        "  check-omp-plugin:\n"
        "    baseUrl: http://127.0.0.1:1/v1\n"
        "    api: openai-completions\n"
        "    auth: none\n"
        "    models:\n"
        "      - id: check-omp-plugin-placeholder\n"
        "        name: Placeholder\n"
        "        api: openai-completions\n"
        "        contextWindow: 8192\n"
        "        maxTokens: 1024\n"
        "        cost:\n"
        "          input: 0\n"
        "          output: 0\n"
        "          cacheRead: 0\n"
        "          cacheWrite: 0\n",
        encoding="utf-8",
    )

    # PATH finds the binary and whatever runtime its shebang names; the rest
    # are the ordinary process furniture a child is entitled to. Nothing here
    # names a provider, a token, or a directory outside `home`.
    env = {name: os.environ[name] for name in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM") if name in os.environ}
    env["HOME"] = str(home)
    # The XDG roots are the other way Omp reaches the machine's own state.
    for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
        env[name] = str(home / name.lower())
    return env


def read_frames(stream, sink: queue.Queue) -> None:
    """Put one parsed stdout frame per line on the queue, then `None` at EOF.

    A thread, because the only other way to read a line under a deadline is a
    non-blocking read loop, and the caller must also be able to drain stdout
    while it waits for the child to exit.
    """
    for line in stream:
        line = line.strip()
        if not line:
            continue
        try:
            sink.put(json.loads(line))
        except json.JSONDecodeError:
            sink.put({"type": "__unparseable__", "line": line})
    sink.put(None)


def ask_for_commands(
    omp: str,
    env: dict[str, str],
    stderr_path: Path,
    plugin_dir: str | None,
    cwd: Path = ROOT,
):
    """Run one `omp --mode rpc` session and return what it offered.

    Returns `(commands, extension_errors, stderr_text)`. The session is asked
    for its commands as soon as the ready frame lands, and stdin is closed as
    soon as the answer does -- the documented shutdown, which drains what Omp
    accepted and exits 0. Reading continues to EOF so an `extension_error`
    raised on shutdown is still seen.
    """
    argv = [omp, "--mode", "rpc"]
    if plugin_dir is not None:
        argv += ["--plugin-dir", plugin_dir]

    with stderr_path.open("w", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_file,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

        frames: queue.Queue = queue.Queue()
        threading.Thread(target=read_frames, args=(process.stdout, frames), daemon=True).start()

        deadline = time.monotonic() + TIMEOUT_SECONDS
        extension_errors: list[dict] = []
        commands: list[dict] | None = None
        ready = False

        def next_frame():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            try:
                return frames.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError from None

        try:
            while True:
                frame = next_frame()
                if frame is None:
                    break

                kind = frame.get("type")
                if kind == "extension_error":
                    extension_errors.append(frame)
                elif kind == "ready" and not ready:
                    ready = True
                    # Asked only once ready, because a command sent before the
                    # ready frame is not guaranteed to be processed.
                    #
                    # Omp can be gone by the time this runs -- it writes the
                    # ready frame before it has a model, and exits a moment
                    # later where it has none -- and the write then raises
                    # rather than returning. Swallowed here so the loop drains
                    # to EOF and the failure is reported as `omp exited
                    # without answering`, with its stderr, instead of as a
                    # traceback that says only `BrokenPipeError`.
                    try:
                        process.stdin.write(json.dumps(REQUEST) + "\n")
                        process.stdin.flush()
                    except (BrokenPipeError, OSError, ValueError):
                        pass
                elif (
                    kind == "response"
                    and frame.get("command") == "get_available_commands"
                    and frame.get("id") == REQUEST_ID
                ):
                    if not frame.get("success"):
                        raise CheckFailed(
                            f"get_available_commands failed: {frame.get('error')}",
                            stderr_path.read_text(encoding="utf-8"),
                        )
                    commands = frame.get("data", {}).get("commands", [])
                    process.stdin.close()

            exit_code = process.wait(timeout=max(deadline - time.monotonic(), 1))
        except TimeoutError:
            process.kill()
            stage = "the get_available_commands response" if ready else "the ready frame"
            raise CheckFailed(
                f"timed out after {TIMEOUT_SECONDS:.0f}s waiting for {stage}",
                stderr_path.read_text(encoding="utf-8"),
            ) from None
        except subprocess.TimeoutExpired:
            process.kill()
            raise CheckFailed(
                "omp did not exit after stdin closed", stderr_path.read_text(encoding="utf-8")
            ) from None
        finally:
            if process.poll() is None:
                process.kill()

        stderr_text = stderr_path.read_text(encoding="utf-8")

    if commands is None:
        raise CheckFailed("omp exited without answering get_available_commands", stderr_text)
    if exit_code != 0:
        raise CheckFailed(f"omp exited {exit_code} after stdin closed", stderr_text)
    return commands, extension_errors, stderr_text


def assert_session(route: str, expected: list[str], result) -> None:
    """The assertions every route shares: the skills, and no runtime error."""
    commands, extension_errors, stderr_text = result

    if extension_errors:
        detail = "; ".join(
            f"{err.get('extensionPath')} on {err.get('event')}: {err.get('error')}" for err in extension_errors
        )
        raise CheckFailed(f"[{route}] extension_error: {detail}", stderr_text)

    offered = {command.get("name") for command in commands}
    missing = [name for name in expected if name not in offered]
    if missing:
        raise CheckFailed(
            f"[{route}] omp did not offer {len(missing)} of {len(expected)} skill commands: "
            f"{', '.join(missing)}",
            stderr_text,
        )


def assert_absent(route: str, forbidden: list[str], result) -> None:
    """Require local-only skills to stay out of plugin discovery."""
    commands, extension_errors, stderr_text = result
    if extension_errors:
        detail = "; ".join(
            f"{err.get('extensionPath')} on {err.get('event')}: {err.get('error')}" for err in extension_errors
        )
        raise CheckFailed(f"[{route}] extension_error: {detail}", stderr_text)

    offered = {command.get("name") for command in commands}
    present = [name for name in forbidden if name in offered]
    if present:
        raise CheckFailed(
            f"[{route}] exposed local-only skill commands: {', '.join(present)}",
            stderr_text,
        )


def link_plugin(omp: str, env: dict[str, str]) -> None:
    """Install this checkout into the throwaway HOME, and check Omp agrees.

    `link` is the offline half of the install route: it symlinks the checkout
    under `~/.omp/plugins/node_modules` and records it in the lockfile, which
    is the shape a marketplace install leaves behind.
    """
    linked = subprocess.run(
        [omp, "plugin", "link", "."],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    if linked.returncode != 0:
        raise CheckFailed(f"omp plugin link failed: {linked.stdout.strip()}", linked.stderr)

    listed = subprocess.run(
        [omp, "plugin", "list"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=TIMEOUT_SECONDS,
    )
    if listed.returncode != 0 or PLUGIN_NAME not in listed.stdout:
        raise CheckFailed(
            f"omp plugin list does not report {PLUGIN_NAME} after link: {listed.stdout.strip()}",
            listed.stderr,
        )


def main() -> None:
    omp = shutil.which("omp")
    if omp is None:
        raise CheckFailed("omp is not on PATH; install it before `make check-omp-plugin`")

    expected = expected_skill_commands()
    if not expected:
        raise CheckFailed("no skills found under skills/; nothing to check")

    local_skill = "skill:fix-daily-driver-bugs"
    if not (ROOT / ".omp/skills/fix-daily-driver-bugs/SKILL.md").is_file():
        raise CheckFailed("the repository-local fix-daily-driver-bugs skill is missing")

    with tempfile.TemporaryDirectory(prefix="check-omp-plugin-") as tmp:
        home = Path(tmp)
        env = isolated_environment(home)
        unrelated = home / "unrelated-project"
        unrelated.mkdir()

        # A repository-local session sees the local skill body and can invoke it.
        local_result = ask_for_commands(omp, env, home / "local-stderr.log", plugin_dir=None, cwd=ROOT)
        assert_session("local", [], local_result)
        local_commands = {command.get("name"): command for command in local_result[0]}
        if local_skill not in local_commands:
            raise CheckFailed("Omp did not discover the repository-local skill", local_result[2])
        skill_body = (ROOT / ".omp/skills/fix-daily-driver-bugs/SKILL.md").read_text(encoding="utf-8")
        if "Promote in place" not in skill_body:
            raise CheckFailed("the repository-local skill body is unreadable or incomplete")

        # Both plugin routes run from outside this repository. The plugin's
        # published skills must load, while the project-local skill stays absent.
        plugin_dir_result = ask_for_commands(
            omp,
            env,
            home / "plugin-dir-stderr.log",
            plugin_dir=str(ROOT),
            cwd=unrelated,
        )
        assert_session("plugin-dir", expected, plugin_dir_result)
        assert_absent("plugin-dir", [local_skill], plugin_dir_result)

        link_plugin(omp, env)
        result = ask_for_commands(omp, env, home / "linked-stderr.log", plugin_dir=None, cwd=unrelated)
        assert_session("linked", expected, result)
        assert_absent("linked", [local_skill], result)
        stderr_text = result[2]
        if LOAD_FAILURE in stderr_text:
            raise CheckFailed("[linked] the Omp extension did not load", stderr_text)

    print(
        f"check-omp-plugin: Omp exposes the readable local skill in this repository, "
        f"keeps it off both plugin routes, and offers all {len(expected)} plugin skills"
    )


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-omp-plugin: {failure}", file=sys.stderr)
        if failure.stderr.strip():
            print("--- omp stderr ---", file=sys.stderr)
            print(failure.stderr.strip(), file=sys.stderr)
        sys.exit(1)
