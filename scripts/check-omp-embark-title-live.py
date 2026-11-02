#!/usr/bin/env python3
"""Exercise the embark title barrier and idle owner reminders in real Omp.

The scripted local model drives the title gate and an idle-owner wake.
A fake `gh` supplies fixtures; no live service is used. The idle scenario
also checks that cancellation prevents another turn. The scripted provider
does not establish how a live model chooses a title or resolves a conflict.
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
REMINDER_QUEUED = threading.Event()


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


def target_from(messages) -> tuple[int, str, int]:
    """Find the latest scenario request, excluding additional context messages."""
    for index in range(len(messages) - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "user":
            continue
        text = text_of(message.get("content"))
        matches = re.findall(r"(?:issue://(?:[^/]+/[^/]+/)?|issues/|#?)(58[23])\b", text)
        if matches:
            return index, text, int(matches[-1])
    raise CheckFailed("scripted model cannot identify a target in user messages")


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
    if index == 6 and number == 582:
        return "daily_driver_schedule", {
            "delaySeconds": 1,
            "message": "Embark #582 watch backstop. Verify the completed gate survives.",
        }
    raise CheckFailed(f"unexpected scripted tool-call index {index}")


class MockModel(BaseHTTPRequestHandler):
    """Prevent command-like timer deliveries from silently reinstating the startup gate."""

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body.get("messages", [])
        last_user, user_text, number = target_from(messages)
        reminder = "watch backstop" in user_text
        repository_qualified = bool(
            re.search(rf"\nUser:\s*issue://example/project/{number}\b", user_text)
        )
        index = sum(
            len(message.get("tool_calls", []))
            for message in messages[last_user + 1 :]
            if message.get("role") == "assistant"
        )
        last = messages[-1] if messages else {}
        if not reminder and last.get("role") == "tool":
            RESULTS[(number, index - 1)] = text_of(last.get("content"))
        if not reminder and number == 582 and index == 7:
            if not REMINDER_QUEUED.wait(timeout=15):
                raise CheckFailed("scheduled reminder did not enter the live follow-up queue")
        if (reminder and index >= 1) or (not reminder and index >= (7 if number == 582 else 6)):
            delta = {"role": "assistant", "content": "Startup title verified."}
            finish = "stop"
        else:
            if reminder:
                name, arguments = "write", {"path": "wake-proof.txt", "content": "gate preserved\n"}
            else:
                name, arguments = tool_call(number, index, repository_qualified)
            delta = {
                "role": "assistant",
                "tool_calls": [{
                    "index": 0,
                    "id": f"{'wake' if reminder else 'embark'}-{number}-{index}",
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

class OwnerModel(BaseHTTPRequestHandler):
    """Expose a lost idle-owner wake without contacting a model service."""

    requests: list[tuple[str, list]] = []

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = body["messages"]
        last_user = next(
            i for i in range(len(messages) - 1, -1, -1)
            if messages[i].get("role") == "user"
            and any(marker in text_of(messages[i].get("content")) for marker in (
                "Observe the offline owner fixture.", "OWNER_WAKE", "CANCEL_PROBE"
            ))
        )
        prompt = text_of(messages[last_user].get("content"))
        calls = sum(len(message.get("tool_calls", [])) for message in messages[last_user + 1 :])
        self.requests.append((prompt, messages))
        tool = None
        if "OWNER_WAKE" in prompt:
            if calls == 0:
                tool = ("read", {"path": "maintenance.json"})
            result = "Maintenance result observed."
        elif "CANCEL_PROBE" in prompt:
            if calls == 0:
                tool = ("daily_driver_schedule", {"delaySeconds": 1, "message": "CANCELLED_WAKE"})
            elif calls == 1:
                contents = (text_of(message.get("content")) for message in reversed(messages))
                match = next((match for content in contents if (match := re.search(r"Scheduled in 1s as (\S+)", content))), None)
                if match is None:
                    raise CheckFailed("scheduled trigger identifier was not returned")
                tool = ("daily_driver_cancel_schedule", {"triggerId": match.group(1)})
            result = "Reminder cancelled."
        else:
            if calls == 0:
                tool = ("daily_driver_schedule", {
                    "delaySeconds": 3,
                    "message": "OWNER_WAKE inspect the offline maintenance result",
                })
            result = "Owner reminder armed."
        if tool:
            delta = {
                "role": "assistant",
                "tool_calls": [{
                    "index": 0, "id": f"owner-{len(self.requests)}", "type": "function",
                    "function": {"name": tool[0], "arguments": json.dumps(tool[1])},
                }],
            }
            finish = "tool_calls"
        else:
            delta = {"role": "assistant", "content": result}
            finish = "stop"
        chunks = [
            {"id": "owner", "object": "chat.completion.chunk", "model": MODEL,
             "choices": [{"index": 0, "delta": delta}]},
            {"id": "owner", "object": "chat.completion.chunk", "model": MODEL,
             "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
        ]
        data = ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def check_idle_owner(omp: str, root: Path) -> None:
    """Catch reminders that arrive after settlement without starting another turn."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), OwnerModel)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        home = root / "owner-home"
        sandbox = root / "owner-sandbox"
        sandbox.mkdir()
        write_home(home, server.server_address[1])
        (sandbox / "maintenance.json").write_text('{"exit": 3, "mergeStateStatus": "DIRTY"}', encoding="utf-8")
        env = {name: os.environ[name] for name in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM") if name in os.environ}
        env["HOME"] = str(home)
        for name in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
            env[name] = str(home / name.lower())
        stderr_path = root / "owner-stderr.log"
        with stderr_path.open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(
                [omp, "--mode", "rpc", "--no-session", "--extension",
                 str(ROOT / "extensions" / "daily-driver.js"), "--tools", "read,write"],
                cwd=sandbox, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=stderr, text=True, encoding="utf-8", bufsize=1,
            )
            frames: queue.Queue = queue.Queue()
            threading.Thread(target=read_frames, args=(process.stdout, frames), daemon=True).start()

            def send(command: dict) -> None:
                process.stdin.write(json.dumps(command) + "\n")
                process.stdin.flush()

            def receive(predicate, seconds: float = 60) -> dict:
                deadline = time.monotonic() + seconds
                while time.monotonic() < deadline:
                    try:
                        frame = frames.get(timeout=max(0.01, deadline - time.monotonic()))
                    except queue.Empty:
                        break
                    if frame is None or frame.get("type") == "extension_error":
                        raise CheckFailed(f"owner session ended unexpectedly: {frame}", stderr_path.read_text())
                    if predicate(frame):
                        return frame
                raise CheckFailed("timed out waiting for idle-owner event", stderr_path.read_text())

            terminal = lambda frame: frame.get("type") == "agent_end" and frame.get("isTerminal", True)
            try:
                receive(lambda frame: frame.get("type") == "ready")
                send({"id": "model", "type": "set_model", "provider": PROVIDER, "modelId": MODEL})
                if not receive(lambda frame: frame.get("id") == "model").get("success"):
                    raise CheckFailed("owner model selection failed", stderr_path.read_text())
                send({"id": "initial", "type": "prompt", "message": "Observe the offline owner fixture."})
                receive(terminal)
                if any("OWNER_WAKE" in prompt for prompt, _ in OwnerModel.requests):
                    raise CheckFailed("owner wake arrived before the initial turn settled")
                receive(terminal)
                if not any("maintenance.json" in json.dumps(messages) and "DIRTY" in json.dumps(messages)
                           for prompt, messages in OwnerModel.requests if "OWNER_WAKE" in prompt):
                    raise CheckFailed("idle wake did not read the maintenance conflict fixture")
                send({"id": "cancel", "type": "prompt", "message": "CANCEL_PROBE stop observation."})
                receive(terminal)
                if not any("Cancelled trigger " in json.dumps(messages)
                           for prompt, messages in OwnerModel.requests if "CANCEL_PROBE" in prompt):
                    raise CheckFailed("reminder cancellation was not confirmed")
                try:
                    receive(lambda frame: frame.get("type") == "agent_start", seconds=2)
                except CheckFailed as failure:
                    if str(failure) != "timed out waiting for idle-owner event":
                        raise
                else:
                    raise CheckFailed("a cancelled reminder started another owner turn")
                if any("CANCELLED_WAKE" in prompt for prompt, _ in OwnerModel.requests):
                    raise CheckFailed("a cancelled reminder reached the owner")
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    finally:
        server.shutdown()


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
        # Keep expanded skills and both scenarios below the compaction threshold.
        "        contextWindow: 131072\n"
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
    """Release the provider only after the real timer queues its reminder."""
    for line in stream:
        line = line.strip()
        if line:
            try:
                frame = json.loads(line)
                if (frame.get("type") == "queue_update"
                        and any("watch backstop" in text for text in frame.get("followUp", []))):
                    REMINDER_QUEUED.set()
                sink.put(frame)
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
                if number == 582:
                    wake = wait_for(
                        lambda frame: frame.get("type") == "tool_execution_end"
                        and frame.get("toolCallId") == "wake-582-0",
                        "the scheduled reminder's guarded write",
                    )
                    if wake.get("isError") or (cwd / "wake-proof.txt").read_text() != "gate preserved\n":
                        raise CheckFailed(f"the reminder reset the gate: {wake!r}", stderr_path.read_text())
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
            check_idle_owner(omp, root)
    finally:
        server.shutdown()
    print("check-omp-embark-title-live: title gates, idle owner wake, and cancellation passed")


if __name__ == "__main__":
    try:
        main()
    except CheckFailed as failure:
        print(f"check-omp-embark-title-live: {failure}", file=sys.stderr)
        if failure.stderr.strip():
            print("--- omp stderr ---", file=sys.stderr)
            print(failure.stderr.strip(), file=sys.stderr)
        sys.exit(1)
