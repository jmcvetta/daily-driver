#!/usr/bin/env python3
"""Exercise the explicit embark title barrier through a linked real Omp.

The scripted local model drives the issue read, blocked unrelated read, exact
`xd://` title write, and resumed read. A fake `gh` supplies issue fixtures; no
GitHub service or paid model is contacted.

This proves event delivery, denial and title application. It does not prove
that a live model chooses the right title wording without the denial guidance.
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

from coder_eval_omp.launch import OMP_CONFIG  # noqa: E402
from coder_eval_omp.tools import select_tools  # noqa: E402

TIMEOUT_SECONDS = 180.0
PROVIDER = "embark-title-probe"
MODEL = "embark-title-probe-model"
TARGETS = {
    582: ("Epic title 582", "⛵ EPIC #582 Epic title 582"),
    583: ("Epic title 583", "⛵ EPIC #583 Epic title 583"),
}
RESULTS: dict[tuple[int, int], str] = {}
RPC_EVENTS: list[dict] = []


class CheckFailed(Exception):
    """An assertion failure with the captured Omp diagnostic text."""

    def __init__(self, message: str, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def text_of(content) -> str:
    """Return text from the Omp message content variants used by RPC."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def target_from(messages) -> int:
    """Find the issue number from the latest request, outside skill examples."""
    latest = next((m for m in reversed(messages) if m.get("role") == "user"), {})
    text = text_of(latest.get("content"))
    matches = re.findall(r"(?:issue://(?:[^/]+/[^/]+/)?|issues/|#?)(58[23])\b", text)
    if not matches:
        raise CheckFailed(f"scripted model cannot identify a target in latest user message: {text[:300]!r}")
    return int(matches[-1])


def tool_call(number: int, index: int, repository_qualified: bool) -> tuple[str, dict]:
    """Return the next guarded call in one scenario."""
    if index == 0:
        return "read", {"path": "prep.md"}
    if index == 1:
        path = f"issue://example/project/{number}" if repository_qualified else f"issue://{number}"
        return "read", {"path": path}
    if index == 2:
        return "read", {"path": "prep.md"}
    if index == 3:
        return "write", {
            "path": "xd://daily_driver_set_session_title",
            "content": json.dumps({"title": TARGETS[number][1]}),
        }
    if index == 4:
        return "read", {"path": "prep.md"}
    if index == 5:
        return "daily_driver_get_session", {}
    raise CheckFailed(f"unexpected scripted tool-call index {index}")


class MockModel(BaseHTTPRequestHandler):
    """An OpenAI-compatible local endpoint that scripts six calls per request."""

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body.get("messages", [])
        number = target_from(messages)
        latest_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        user_text = text_of(latest_user.get("content"))
        repository_qualified = bool(
            re.search(rf"\nUser:\s*issue://example/project/{number}\b", user_text)
        )
        last_user = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)
        index = sum(
            len(message.get("tool_calls", []))
            for message in messages[last_user + 1 :]
            if message.get("role") == "assistant"
        )
        last = messages[-1] if messages else {}
        if last.get("role") == "tool":
            RESULTS[(number, index - 1)] = text_of(last.get("content"))
        if index >= 6:
            delta = {"role": "assistant", "content": "Startup title verified."}
            finish = "stop"
        else:
            name, arguments = tool_call(number, index, repository_qualified)
            delta = {
                "role": "assistant",
                "tool_calls": [{
                    "index": 0,
                    "id": f"embark-{number}-{index}",
                    "type": "function",
                    "function": {"name": name, "arguments": json.dumps(arguments)},
                }],
            }
            finish = "tool_calls"
        chunks = [
            {"id": "embark-title", "object": "chat.completion.chunk", "model": MODEL,
             "choices": [{"index": 0, "delta": delta}]},
            {"id": "embark-title", "object": "chat.completion.chunk", "model": MODEL,
             "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ]
        payload = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def write_home(home: Path, port: int) -> None:
    """Configure an isolated Omp home with only the local scripted model."""
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
        "        name: Embark title probe\n"
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


def write_fake_gh(bin_dir: Path) -> None:
    """Return deterministic epic fixtures for Omp's native issue:// protocol."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    fake = bin_dir / "gh"
    rows = []
    for number, (title, _session_title) in TARGETS.items():
        rows.append(
            f"  *{number}*) printf '%s\\n' "
            + "'"
            + json.dumps({
                "author": {"login": "fixture"},
                "body": "Fixture epic body.",
                "comments": [],
                "createdAt": "2026-01-01T00:00:00Z",
                "labels": [{"name": "epic"}],
                "number": number,
                "state": "OPEN",
                "stateReason": "",
                "title": title,
                "updatedAt": "2026-01-01T00:00:00Z",
                "url": f"https://github.com/example/project/issues/{number}",
            })
            + "' ; exit 0 ;;\n"
        )
    fake.write_text(
        "#!/bin/sh\n"
        "case \" $* \" in\n"
        + "".join(rows)
        + "  *) printf '%s\\n' 'unexpected fake gh invocation' >&2; exit 2 ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)


def read_frames(stream, sink: queue.Queue) -> None:
    """Queue parsed RPC frames until Omp closes stdout."""
    for line in stream:
        line = line.strip()
        if line:
            try:
                sink.put(json.loads(line))
            except json.JSONDecodeError:
                continue
    sink.put(None)


def run(omp: str, env: dict[str, str], cwd: Path, stderr_path: Path) -> None:
    """Drive plain and expanded-skill activation in one linked Omp session."""
    argv = [omp, "--mode", "rpc", *select_tools(["Read", "Write"], None).argv]
    with stderr_path.open("w", encoding="utf-8") as stderr_file:
        process = subprocess.Popen(
            argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=stderr_file, text=True, encoding="utf-8", bufsize=1,
        )
        frames: queue.Queue = queue.Queue()
        threading.Thread(target=read_frames, args=(process.stdout, frames), daemon=True).start()
        deadline = time.monotonic() + TIMEOUT_SECONDS

        def wait_for(predicate, what: str) -> dict:
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
                RPC_EVENTS.append(frame)
                if predicate(frame):
                    return frame

        def send(command: dict) -> None:
            process.stdin.write(json.dumps(command) + "\n")
            process.stdin.flush()

        try:
            wait_for(lambda frame: frame.get("type") == "ready", "the ready frame")
            send({"id": "model", "type": "set_model", "provider": PROVIDER, "modelId": MODEL})
            model = wait_for(lambda frame: frame.get("type") == "response" and frame.get("id") == "model", "set_model")
            if not model.get("success"):
                raise CheckFailed(f"set_model failed: {model.get('error')}", stderr_path.read_text(encoding="utf-8"))
            for number, prompt in (
                (582, "embark 582. Exercise the explicit startup barrier."),
                (583, "/skill:embark issue://example/project/583"),
            ):
                send({"id": f"scenario-{number}", "type": "prompt", "message": prompt})
                wait_for(
                    lambda frame: frame.get("type") == "agent_end" and frame.get("isTerminal", True),
                    f"scenario {number} to settle",
                )
            process.stdin.close()
            process.wait(timeout=max(deadline - time.monotonic(), 1))
        finally:
            if process.poll() is None:
                process.kill()


def main() -> None:
    omp = shutil.which("omp")
    if omp is None:
        raise CheckFailed("omp is not on PATH; install it before `make check-omp-embark-title-live`")
    server = ThreadingHTTPServer(("127.0.0.1", 0), MockModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="check-omp-embark-title-") as tmp:
            root = Path(tmp)
            home = root / "home"
            sandbox = root / "sandbox"
            bin_dir = root / "bin"
            sandbox.mkdir()
            prep_content = "read-only preparation and resumed read fixture\n"
            (sandbox / "prep.md").write_text(prep_content, encoding="utf-8")
            write_home(home, server.server_address[1])
            write_fake_gh(bin_dir)
            original_path = os.environ.get("PATH", "")
            env = {name: os.environ[name] for name in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM") if name in os.environ}
            env["PATH"] = f"{bin_dir}:{original_path}"
            env["HOME"] = str(home)
            for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
                env[name] = str(home / name.lower())
            linked = subprocess.run(
                [omp, "plugin", "link", str(ROOT)], cwd=ROOT, env=env,
                capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
            )
            if linked.returncode != 0:
                raise CheckFailed(f"omp plugin link failed: {linked.stdout.strip()}", linked.stderr)
            listed = subprocess.run([omp, "plugin", "list"], cwd=sandbox, env=env,
                                    capture_output=True, text=True, timeout=TIMEOUT_SECONDS)
            if listed.returncode != 0 or "daily-driver" not in listed.stdout:
                raise CheckFailed("Omp did not report the linked plugin", listed.stderr)
            stderr_path = root / "omp-stderr.log"
            run(omp, env, sandbox, stderr_path)
            stderr = stderr_path.read_text(encoding="utf-8")
            for number in TARGETS:
                issue_read = RESULTS.get((number, 1), "")
                denial = RESULTS.get((number, 2), "")
                session = RESULTS.get((number, 5), "")
                event_results = {
                    event.get("toolCallId"): event
                    for event in RPC_EVENTS
                    if event.get("type") == "tool_execution_end"
                }
                for index in (0, 4):
                    call_id = f"embark-{number}-{index}"
                    event = event_results.get(call_id, {})
                    result = event.get("result", {})
                    if prep_content.strip() not in text_of(result.get("content")):
                        raise CheckFailed(
                            f"issue {number}: read-only prep call {index} did not return fixture content: {event!r}",
                            stderr,
                        )
                denied = event_results.get(f"embark-{number}-2", {})
                if not denied.get("isError"):
                    raise CheckFailed(f"issue {number}: unrelated read was not blocked after identity: {denied!r}", stderr)
                if f"# Issue #{number}:" not in issue_read:
                    raise CheckFailed(
                        f"issue {number}: canonical issue read did not return metadata: {issue_read[:500]!r}",
                        stderr,
                    )
                if "requested epic" not in denial.lower() and "⛵ epic" not in denial.lower():
                    raise CheckFailed(
                        f"issue {number}: unrelated read was not denied by the title barrier: {denial[:500]!r}; "
                        f"issue-read result: {issue_read[:500]!r}",
                        stderr,
                    )
                if TARGETS[number][1] not in session:
                    raise CheckFailed(f"issue {number}: session name does not carry the requested epic title: {session[:500]!r}", stderr)
    finally:
        server.shutdown()
    print("check-omp-embark-title-live: linked Omp enforced the first-read deadline, applied both epic titles, and resumed the blocked reads")


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-omp-embark-title-live: {failure}", file=sys.stderr)
        if failure.stderr.strip():
            print("--- omp stderr ---", file=sys.stderr)
            print(failure.stderr.strip(), file=sys.stderr)
        sys.exit(1)
