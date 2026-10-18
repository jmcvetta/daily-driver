#!/usr/bin/env python3
"""Prove that a real Omp loads the eval guard and honours what it refuses.

`check-omp-eval-guard.mjs` drives `eval_guard.js` with a fake `pi`. That proves
the guard's logic and nothing about Omp: it never starts Omp, so a guard that
`-e` does not load, or whose refusal Omp ignores, passes it green. Nor can it
see `fetch.enabled: false`, which is Omp's own setting.

This is the other half. It starts `omp --mode rpc` the way the `omp` agent kind
does -- `launch.rpc_argv`, `launch.child_env` and `launch.OMP_CONFIG`, with the
plugin linked -- against a local mock model that scripts one tool call per
prompt and records what each call returned.

WHAT IT ASSERTS

    File tools cannot return host, sibling or provider bytes in either arm,
    including through selectors, compound paths and symlinks. Task files and
    treated skill/reference reads still succeed. The bare registry stays empty.
    Existing scheme and ungranted-write refusals still hold with the plugin.
    `read xd://` lists the plugin devices, so the extension and guard load together.

    Every refusal is produced before any request leaves the machine, so nothing
    here depends on a remote answer. The mock model is the only server, and it
    listens on 127.0.0.1.

WHAT IT DOES NOT ASSERT

    That a real model chooses these calls. The mock chooses them.

Omp on `PATH` is the one thing it needs, which is why it sits outside `make
check`, beside `check-omp-plugin`. No third-party imports.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals" / "coder-eval-omp" / "src"))

from coder_eval_omp.launch import OMP_CONFIG, child_env, rpc_argv  # noqa: E402
from coder_eval_omp.tools import select_tools  # noqa: E402

TIMEOUT_SECONDS = 180.0
PROVIDER = "guard-probe"
MODEL = "guard-probe-model"
INSIDE_TEXT = "inside the sandbox"

#: Prompt -> (the tool call the mock makes, what its result must contain).
PROBES: dict[str, tuple[str, dict, str]] = {
    "probe-pr": ("read", {"path": "pr://o/r/1"}, "pr:// is outside this eval's sandbox"),
    "probe-issue": ("grep", {"pattern": "x", "path": "issue://o/r/1"}, "issue:// is outside this eval's sandbox"),
    "probe-https": ("read", {"path": "https://example.com/"}, "https:// is outside this eval's sandbox"),
    "probe-write": ("write", {"path": "pwned.txt", "content": "x"}, "limits `write` to xd:// devices"),
    "probe-inside": ("read", {"path": "inside.txt"}, INSIDE_TEXT),
    "probe-devices": ("read", {"path": "xd://"}, "daily_driver_set_session_title"),
}


class CheckFailed(Exception):
    """A failed assertion, with the stderr that explains it."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def text_of(content) -> str:
    """A chat message's content as plain text, whichever shape it arrived in."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


class MockModel(BaseHTTPRequestHandler):
    """An OpenAI-compatible chat endpoint that scripts one tool call per probe.

    A request whose last message is the user's gets that probe's tool call; a
    request whose last message is a tool result gets that result recorded and
    a closing line of text.
    """

    results: dict[str, str] = {}

    def log_message(self, *args) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body.get("messages", [])
        last = messages[-1] if messages else {}
        # Omp prepends a system reminder to the first prompt, so the probe is
        # found by its name rather than taken as the whole message.
        user = next((text_of(m.get("content")) for m in reversed(messages) if m.get("role") == "user"), "")
        found = re.findall(r"probe-[a-z]+", user)
        probe = found[-1] if found else ""
        if last.get("role") == "tool":
            MockModel.results[probe] = text_of(last.get("content"))
            delta = {"role": "assistant", "content": "done"}
            finish = "stop"
        else:
            tool, arguments, _ = PROBES.get(probe, ("read", {"path": "inside.txt"}, ""))
            delta = {
                "role": "assistant",
                "tool_calls": [
                    {
                        "index": 0,
                        "id": f"call-{probe}",
                        "type": "function",
                        "function": {"name": tool, "arguments": json.dumps(arguments)},
                    }
                ],
            }
            finish = "tool_calls"
        chunks = [
            {"id": "c", "object": "chat.completion.chunk", "model": MODEL, "choices": [{"index": 0, "delta": delta}]},
            {
                "id": "c",
                "object": "chat.completion.chunk",
                "model": MODEL,
                "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        ]
        payload = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def write_home(home: Path, port: int) -> None:
    """The throwaway Omp home: the agent kind's config, and the mock as its one model."""
    agent = home / ".omp" / "agent"
    agent.mkdir(parents=True, exist_ok=True)
    (agent / "config.yml").write_text(OMP_CONFIG, encoding="utf-8")
    (agent / "models.yml").write_text(
        "providers:\n"
        f"  {PROVIDER}:\n"
        f"    baseUrl: http://127.0.0.1:{port}/v1\n"
        "    api: openai-completions\n"
        "    auth: none\n"
        "    models:\n"
        f"      - id: {MODEL}\n"
        "        name: Guard probe\n"
        "        api: openai-completions\n"
        "        contextWindow: 1048576\n"
        "        maxTokens: 1024\n"
        "        cost:\n"
        "          input: 0\n"
        "          output: 0\n"
        "          cacheRead: 0\n"
        "          cacheWrite: 0\n",
        encoding="utf-8",
    )


def read_frames(stream, sink: queue.Queue) -> None:
    """Put one parsed stdout frame per line on the queue, then `None` at EOF."""
    for line in stream:
        line = line.strip()
        if line:
            try:
                sink.put(json.loads(line))
            except json.JSONDecodeError:
                pass
    sink.put(None)


def run_probes(omp: str, env: dict[str, str], sandbox: Path, stderr_path: Path) -> None:
    """Send each probe as one prompt and wait for its turn to settle."""
    argv = rpc_argv(omp, select_tools(["Read", "Grep", "Glob"], None), ["--no-title"])
    with stderr_path.open("w", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            argv,
            cwd=sandbox,
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

        def wait_for(matches, what: str) -> dict:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise CheckFailed(f"timed out waiting for {what}", stderr_path.read_text(encoding="utf-8"))
                try:
                    frame = frames.get(timeout=remaining)
                except queue.Empty:
                    continue
                if frame is None:
                    raise CheckFailed(f"omp exited before {what}", stderr_path.read_text(encoding="utf-8"))
                if frame.get("type") == "extension_error":
                    raise CheckFailed(f"extension_error: {frame}", stderr_path.read_text(encoding="utf-8"))
                if matches(frame):
                    return frame

        def send(command: dict) -> None:
            process.stdin.write(json.dumps(command) + "\n")
            process.stdin.flush()

        try:
            wait_for(lambda f: f.get("type") == "ready", "the ready frame")
            send({"id": "model", "type": "set_model", "provider": PROVIDER, "modelId": MODEL})
            answer = wait_for(lambda f: f.get("type") == "response" and f.get("id") == "model", "set_model")
            if not answer.get("success"):
                raise CheckFailed(f"set_model failed: {answer.get('error')}", stderr_path.read_text(encoding="utf-8"))
            send({"id": "commands", "type": "get_available_commands"})
            registry = wait_for(lambda f: f.get("type") == "response" and f.get("id") == "commands", "commands")
            skills = [entry for entry in registry.get("data", {}).get("commands", []) if entry["name"].startswith("skill:")]
            if bool(skills) != ("probe-skill" in PROBES):
                raise CheckFailed(f"unexpected skill registry: {skills}", stderr_path.read_text(encoding="utf-8"))
            for probe in PROBES:
                send({"id": probe, "type": "prompt", "message": probe})
                wait_for(lambda f: f.get("type") == "agent_end" and f.get("isTerminal", True), f"{probe} to settle")
            process.stdin.close()
            process.wait(timeout=max(deadline - time.monotonic(), 1))
        finally:
            if process.poll() is None:
                process.kill()


def main() -> None:
    omp = shutil.which("omp")
    if omp is None:
        raise CheckFailed("omp is not on PATH; install it before `make check-omp-eval-guard-live`")

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="check-omp-eval-guard-") as tmp:
            original = dict(PROBES)
            protected = "PROTECTED-REPLICATE-AND-PROVIDER-BYTES"
            outside = Path(tmp) / "sibling"
            outside.mkdir()
            (outside / "task.json").write_text(protected, encoding="utf-8")
            (Path(tmp) / "environment.json").write_text(protected, encoding="utf-8")
            for variant in ("bare", "with-plugin"):
                home = Path(tmp) / variant / "home"
                sandbox = Path(tmp) / variant / "sandbox"
                sandbox.mkdir(parents=True)
                (sandbox / "inside.txt").write_text(INSIDE_TEXT + "\nsecond line\n", encoding="utf-8")
                (sandbox / "escape").symlink_to(outside, target_is_directory=True)
                write_home(home, server.server_address[1])
                provider = home / ".omp" / "agent" / "secrets.yml"
                provider.write_text(protected, encoding="utf-8")

                # Never inherit a real provider credential or parent bridge.
                base = {name: os.environ[name] for name in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM") if name in os.environ}
                plugins = [ROOT] if variant == "with-plugin" else []
                env = child_env(base, home, [], select_tools(["Read", "Grep", "Glob"], None),
                                task_root=sandbox, plugin_roots=plugins)
                if plugins:
                    linked = subprocess.run(
                        [omp, "plugin", "link", str(ROOT)], cwd=ROOT, env=env, capture_output=True, text=True,
                        timeout=TIMEOUT_SECONDS,
                    )
                    if linked.returncode != 0:
                        raise CheckFailed(f"omp plugin link failed: {linked.stdout.strip()}", linked.stderr)

                PROBES.clear()
                PROBES.update(original)
                if not plugins:
                    del PROBES["probe-devices"]
                    # No extension devices means Omp offers no device-only write.
                    del PROBES["probe-write"]
                refusal = "eval read boundary refuses"
                # These calls previously leaked host treatment, sibling answers
                # and provider bytes while still earning normal trigger credit.
                for name, path in {
                    "metadata": "../../environment.json",
                    "sibling": str(outside / "task.json"),
                    "selector": f"{outside}/task.json:1:raw",
                    "compound": f"inside.txt;{outside}/task.json",
                    "provider": str(provider),
                    "symlink": "escape/task.json",
                    "uritraversal": "skill://undertake/%2e%2e/%2e%2e/evals/README.md",
                }.items():
                    PROBES[f"probe-{name}"] = ("read", {"path": path}, refusal)
                PROBES["probe-grep"] = ("grep", {"path": str(outside), "pattern": "PROTECTED"}, refusal)
                PROBES["probe-glob"] = ("glob", {"path": str(outside / "*")}, refusal)
                PROBES["probe-descendant"] = ("grep", {"path": ".", "pattern": "PROTECTED"}, refusal)
                PROBES["probe-lines"] = ("read", {"path": "inside.txt:2:raw"}, "second line")
                PROBES["probe-hostsource"] = (
                    "read", {"path": str(ROOT / "skills/undertake/SKILL.md")},
                    "name: undertake" if plugins else refusal,
                )
                if plugins:
                    PROBES["probe-skill"] = ("read", {"path": "skill://undertake"}, "name: undertake")
                    PROBES["probe-reference"] = (
                        "read", {"path": "skill://undertake/references/omp.md:1-5"}, "Omp routes",
                    )
                else:
                    PROBES["probe-bareskill"] = ("read", {"path": "skill://undertake"}, refusal)

                MockModel.results.clear()
                stderr_path = Path(tmp) / f"{variant}-omp-stderr.log"
                run_probes(omp, env, sandbox, stderr_path)
                stderr_text = stderr_path.read_text(encoding="utf-8")
                for probe, (tool, arguments, expected) in PROBES.items():
                    got = MockModel.results.get(probe)
                    if got is None or expected not in got or protected in got:
                        raise CheckFailed(
                            f"{variant}/{probe}: {tool} {json.dumps(arguments)} must return {expected!r} "
                            f"without protected bytes, got {str(got)[:400]!r}", stderr_text,
                        )
                if (sandbox / "pwned.txt").exists():
                    raise CheckFailed("probe-write: the refused write still created pwned.txt", stderr_text)
                print(f"check-omp-eval-guard-live: {variant}: {len(PROBES)} offline probes passed")
    finally:
        server.shutdown()

    print("check-omp-eval-guard-live: both arms preserve legitimate reads without exposing protected bytes")


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-omp-eval-guard-live: {failure}", file=sys.stderr)
        if failure.stderr.strip():
            print("--- omp stderr ---", file=sys.stderr)
            print(failure.stderr.strip(), file=sys.stderr)
        sys.exit(1)
