#!/usr/bin/env python3
"""Exercise the embark title barrier and idle owner reminders in real Omp.

The scripted local model drives the title gate and an idle-owner wake.
A fake `gh` supplies fixtures and records attributed reports; no live service
is used. The idle scenario also checks cancellation. The scripted provider
does not establish how a live model chooses a title or resolves a conflict.

Literal `report_issue` admission belongs to the offline extension fixture:
no disposable override for the harness command is established here, so this
probe must not invoke a potentially real harness report.
"""

from __future__ import annotations

import json
import os
import queue
import re
import shlex
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

TIMEOUT_SECONDS = 300.0
PROVIDER = "embark-title-probe"
MODEL = "embark-title-probe-model"
TARGETS = {
    582: ("Epic title 582", "⛵ EPIC #582 Epic title 582"),
    583: ("Epic title 583", "⛵ EPIC #583 Epic title 583"),
}
SCENARIOS = [
    (582, "bash-help"),
    (583, "bash-help"),
    (582, "eval-single"),
    (583, "eval-double"),
    (582, "bash-positional"),
    (583, "bash-positional"),
    (582, "bash-json-short"),
    (583, "bash-json-long"),
    (582, "direct"),
]
RESULTS: dict[tuple[str, str], str] = {}
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


def target_from(messages) -> int:
    """Find the issue number from the latest request, outside skill examples."""
    latest = next((m for m in reversed(messages) if m.get("role") == "user"), {})
    text = text_of(latest.get("content"))
    matches = re.findall(r"(?:issue://(?:[^/]+/[^/]+/)?|issues/|#?)(58[23])\b", text)
    if not matches:
        raise CheckFailed(f"scripted model cannot identify a target in latest user message: {text[:300]!r}")
    return int(matches[-1])


def scenario_calls(number: int, route: str, repository_qualified: bool) -> list[tuple]:
    """Catch outer recovery routes that admit work without an actual rename."""
    title = TARGETS[number][1]
    setter = f"daily_driver_set_session_title {shlex.quote(title)}"
    calls = []

    def add(label, tool, arguments, expected="allowed"):
        calls.append((label, tool, arguments, expected))

    def pending(label):
        add(label, "write", {"path": "forbidden-write.txt", "content": "must stay blocked"}, "blocked")

    def reports(state):
        for surface in ("direct", "bash"):
            for failure in (False, True):
                label = f"{state}-{surface}-report" + ("-failure" if failure else "")
                arguments = {"args": [
                    "issue", "create", "--repo", "jmcvetta/daily-driver",
                    "--label", "bug", "--title", label,
                    "--body", f"Offline title recovery report.\nEpic {number}; {label}.",
                ]}
                if surface == "direct":
                    add(label, "daily_driver_gh_write", arguments, "report-failure" if failure else "report")
                else:
                    command = "daily_driver_gh_write -j " + shlex.quote(json.dumps(arguments))
                    add(label, "bash", {"command": command}, "report-failure" if failure else "report")
                pending(label + "-pending")
        add(state + "-report-session", "daily_driver_get_session", {})

    add("preparation", "read", {"path": "prep.md"})
    add("initial-session", "daily_driver_get_session", {})
    if route == "bash-help" and number == 582:
        reports("awaiting")
        pending("awaiting-write")
        add("awaiting-title", "daily_driver_set_session_title", {"title": title}, "blocked")
    path = f"issue://example/project/{number}" if repository_qualified else f"issue://{number}"
    add("identity", "read", {"path": path})
    add("required-read", "read", {"path": "prep.md"}, "blocked")
    add("help", "bash", {"command": "daily_driver_set_session_title --help"})
    pending("help-pending")
    add("help-session", "daily_driver_get_session", {})
    if route == "bash-help" and number == 582:
        reports("required")
        add("required-dispatch", "task", {
            "tasks": [{"task": "Write forbidden-dispatch.txt in the sandbox."}],
        }, "blocked")
        add("ordinary-comment", "daily_driver_gh_write", {
            "args": ["issue", "comment", "582", "--repo", "jmcvetta/daily-driver", "--body", "not a report"],
        }, "blocked")
        add("direct-gh", "bash", {
            "command": "gh issue create --repo jmcvetta/daily-driver --label bug --title forbidden --body forbidden",
        }, "blocked")
        for index, command in enumerate((
            f"printf '%s' {shlex.quote(setter)}",
            setter + "; printf forbidden",
            setter + " | cat",
            setter + " > forbidden-redirection.txt",
            "(" + setter + ")",
            "TITLE=forbidden " + setter,
            "daily_driver_set_session_title \"$(printf forbidden)\"",
            "daily_driver_set_session_title \"$HOME\"",
            "daily_driver_set_session_title --help && " + setter + " && printf forbidden",
        )):
            add(f"negative-shell-{index}", "bash", {"command": command}, "blocked")
        for index, code in enumerate((
            f"const title = {json.dumps(title)}; await tool.daily_driver_set_session_title({{title}});",
            f"await tool.daily_driver_set_session_title({{['title']: {json.dumps(title)}}});",
            f"await tool.daily_driver_set_session_title({{title: {json.dumps(title)}, extra: true}});",
            f"await tool.daily_driver_set_session_title({{title: `{title}`}});",
            f"await tool.daily_driver_set_session_title({{title: {json.dumps(title)}}}); await tool.read({{path:'prep.md'}});",
        )):
            add(f"negative-eval-{index}", "eval", {"language": "js", "code": code}, "blocked")
        for index, invalid in enumerate((
            TARGETS[583][1], f"⛵ EPIC #{number} ", json.dumps({"title": title}), json.dumps([title]),
        )):
            if index % 2:
                add(f"invalid-title-{index}", "eval", {
                    "language": "js",
                    "code": f"await tool.daily_driver_set_session_title({{title: {json.dumps(invalid)}}});",
                }, "invalid")
            else:
                add(f"invalid-title-{index}", "bash", {
                    "command": "daily_driver_set_session_title " + shlex.quote(invalid),
                }, "invalid")
            pending(f"invalid-title-{index}-pending")
            add(f"invalid-title-{index}-session", "daily_driver_get_session", {})
    if route == "bash-help":
        tool, arguments = "bash", {"command": "daily_driver_set_session_title --help && " + setter}
    elif route == "bash-positional":
        tool, arguments = "bash", {"command": setter}
    elif route.startswith("bash-json-"):
        flag = "-j" if route == "bash-json-short" else "--json"
        tool, arguments = "bash", {
            "command": f"daily_driver_set_session_title {flag} " + shlex.quote(json.dumps({"title": title})),
        }
    elif route.startswith("eval-"):
        literal = "'" + title + "'" if route == "eval-single" else json.dumps(title)
        tool, arguments = "eval", {
            "language": "js", "code": f"await tool.daily_driver_set_session_title({{title: {literal}}});",
        }
    else:
        tool, arguments = "daily_driver_set_session_title", {"title": title}
    add("rename", tool, arguments)
    add("resumed-read", "read", {"path": "prep.md"})
    add("renamed-session", "daily_driver_get_session", {})
    if route == "bash-help" and number == 582:
        add("reminder", "daily_driver_schedule", {
            "delaySeconds": 1,
            "message": "Embark #582 watch backstop. Verify the completed gate survives.",
        })
    return calls


def tool_call(number: int, index: int, route: str, repository_qualified: bool) -> tuple[str, dict]:
    """Return the next real tool call, without altering startup fixture state."""
    _label, name, arguments, _expected = scenario_calls(number, route, repository_qualified)[index]
    return name, arguments


class MockModel(BaseHTTPRequestHandler):
    """Prevent command-like timer deliveries from silently reinstating the startup gate."""

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        messages = body.get("messages", [])
        try:
            number = target_from(messages)
        except CheckFailed:
            # Omp may make independent title-generation requests to the same
            # local provider; they do not belong to a scripted scenario.
            response = {"id": "auxiliary", "object": "chat.completion.chunk", "model": MODEL,
                        "choices": [{"index": 0, "delta": {"content": "391"}, "finish_reason": "stop"}]}
            encoded = (f"data: {json.dumps(response)}\n\ndata: [DONE]\n\n").encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
            return
        latest_user = next((m for m in reversed(messages) if m.get("role") == "user"), {})
        user_text = text_of(latest_user.get("content"))
        reminder = "watch backstop" in user_text
        route_match = re.search(r"\[probe:([a-z-]+)\]", user_text)
        route = route_match.group(1) if route_match else "bash-help"
        scenario = f"{number}-{route}"
        calls = scenario_calls(number, route, repository_qualified=False)
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
        if not reminder and last.get("role") == "tool":
            RESULTS[(scenario, calls[index - 1][0])] = text_of(last.get("content"))
        if not reminder and number == 582 and route == "bash-help" and index == len(calls):
            if not REMINDER_QUEUED.wait(timeout=15):
                raise CheckFailed("scheduled reminder did not enter the live follow-up queue")
        if (reminder and index >= 1) or (not reminder and index >= len(calls)):
            delta = {"role": "assistant", "content": "Startup title verified."}
            finish = "stop"
        else:
            if reminder:
                name, arguments = "write", {"path": "wake-proof.txt", "content": "gate preserved\n"}
            else:
                name, arguments = tool_call(number, index, route, repository_qualified)
            delta = {
                "role": "assistant",
                "tool_calls": [{
                    "index": 0,
                    "id": f"{'wake' if reminder else 'embark'}-{scenario}-{index}",
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
        last_user = max(i for i, message in enumerate(messages) if message.get("role") == "user")
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
    """Record real attributed writes and return offline metadata or failures."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    fixtures = {}
    for number, (title, _session_title) in TARGETS.items():
        fixtures[str(number)] = {
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
        }
    fake = bin_dir / "gh"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "from pathlib import Path\n"
        f"fixtures = {fixtures!r}\n"
        f"recording = Path({str(bin_dir.parent / 'gh-records.jsonl')!r})\n"
        + """
args = sys.argv[1:]
if args[:2] == ["issue", "create"]:
    title = args[args.index("--title") + 1] if "--title" in args else ""
    code = 17 if title.endswith("-failure") else 0
    with recording.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"args": args, "code": code}) + "\\n")
    if code:
        print("offline gh refusal: " + title, file=sys.stderr)
    else:
        print("https://github.com/jmcvetta/daily-driver/issues/9001")
    sys.exit(code)
if args[:2] == ["issue", "view"]:
    for argument in args[2:]:
        number = argument.rsplit("/", 1)[-1]
        if number in fixtures:
            print(json.dumps(fixtures[number]))
            sys.exit(0)
print("unexpected fake gh invocation: " + repr(args), file=sys.stderr)
sys.exit(2)
""",
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
    argv = [omp, "--mode", "rpc", "--tools", "read,write,bash,eval,task"]
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
            for number, route in SCENARIOS:
                scenario = f"{number}-{route}"
                prompt = (
                    f"/skill:embark issue://example/project/{number} [probe:{route}]"
                    if number == 583 else
                    f"embark {number}. Exercise the explicit startup barrier. [probe:{route}]"
                )
                send({"id": scenario, "type": "prompt", "message": prompt})
                if number == 582 and route == "bash-help":
                    wake = wait_for(
                        lambda frame: frame.get("type") == "tool_execution_end"
                        and frame.get("toolCallId") == "wake-582-bash-help-0",
                        "the scheduled reminder's guarded write",
                    )
                    if wake.get("isError") or (cwd / "wake-proof.txt").read_text() != "gate preserved\n":
                        raise CheckFailed(f"the reminder reset the gate: {wake!r}", stderr_path.read_text())
                wait_for(
                    lambda frame: frame.get("type") == "agent_end" and frame.get("isTerminal", True),
                    f"scenario {scenario} to settle",
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
            event_results = {
                event.get("toolCallId"): event
                for event in RPC_EVENTS
                if event.get("type") == "tool_execution_end"
            }
            for number, route in SCENARIOS:
                scenario = f"{number}-{route}"
                initial = RESULTS.get((scenario, "initial-session"))
                for index, (label, _tool, _arguments, expected) in enumerate(
                    scenario_calls(number, route, repository_qualified=number == 583)
                ):
                    event = event_results.get(f"embark-{scenario}-{index}")
                    if event is None:
                        raise CheckFailed(f"{scenario}/{label}: no tool execution result", stderr)
                    result = RESULTS.get((scenario, label), "")
                    if expected == "blocked":
                        if not event.get("isError") or not re.search(r"epic|embark|requested issue", result, re.IGNORECASE):
                            raise CheckFailed(f"{scenario}/{label}: startup barrier did not deny the call: {event!r}", stderr)
                    elif expected == "report-failure":
                        if (not event.get("isError") or "offline gh refusal: " + label not in result
                                or "issues/9001" in result):
                            raise CheckFailed(f"{scenario}/{label}: report failure was hidden: {event!r}", stderr)
                    elif expected == "report":
                        if event.get("isError") or "issues/9001" not in result:
                            raise CheckFailed(f"{scenario}/{label}: report did not reach fake gh: {event!r}", stderr)
                    # Eval may return an inner setter error as an outer result.
                    # The following pending write and name checks catch any
                    # invalid title that changes the session or opens the gate.
                    elif expected != "invalid" and event.get("isError"):
                        raise CheckFailed(f"{scenario}/{label}: admitted call failed: {event!r}", stderr)
                    if label in ("preparation", "resumed-read") and prep_content.strip() not in result:
                        raise CheckFailed(f"{scenario}/{label}: fixture read did not execute: {event!r}", stderr)
                    if label == "identity" and f"# Issue #{number}:" not in result:
                        raise CheckFailed(f"{scenario}: canonical metadata was not read: {result[:500]!r}", stderr)
                    if label.endswith("-session") and label != "renamed-session":
                        if initial is None or result != initial:
                            raise CheckFailed(f"{scenario}/{label}: pending recovery changed the session: {result!r}", stderr)
                session = RESULTS.get((scenario, "renamed-session"), "")
                if TARGETS[number][1] not in session:
                    raise CheckFailed(f"{scenario}: actual session title does not match: {session[:500]!r}", stderr)
            for filename in ("forbidden-write.txt", "forbidden-dispatch.txt", "forbidden-redirection.txt"):
                if (sandbox / filename).exists():
                    raise CheckFailed(f"pending recovery executed an unrelated mutation: {filename}", stderr)
            records_path = root / "gh-records.jsonl"
            records = [json.loads(line) for line in records_path.read_text().splitlines()] if records_path.exists() else []
            reports = [
                (label, arguments if tool == "daily_driver_gh_write" else json.loads(shlex.split(arguments["command"])[2]))
                for label, tool, arguments, expected in scenario_calls(582, "bash-help", False)
                if expected in ("report", "report-failure")
            ]
            if len(records) != len(reports):
                raise CheckFailed(f"expected {len(reports)} attributed reports, recorded {records!r}", stderr)
            for record, (label, arguments) in zip(records, reports):
                args = record["args"]
                intended = arguments["args"]
                body_index = intended.index("--body") + 1
                if args[:body_index] != intended[:body_index] or args[body_index + 1:] != intended[body_index + 1:]:
                    raise CheckFailed(f"{label}: report operands changed: {args!r}", stderr)
                body = args[body_index]
                if not body.startswith(intended[body_index] + "\n"):
                    raise CheckFailed(f"{label}: report body lost its literal message: {body!r}", stderr)
                for field, value in (("Model", MODEL), ("Provider", PROVIDER)):
                    if body.count(f"\n{field}: {value}\n") != 1:
                        raise CheckFailed(f"{label}: missing or duplicate {field} provenance: {body!r}", stderr)
                if len(re.findall(r"\nHarness: Omp [^\n]+\nSession: [^\n]+", body)) != 1:
                    raise CheckFailed(f"{label}: missing harness/session provenance: {body!r}", stderr)
                if record["code"] != (17 if label.endswith("-failure") else 0):
                    raise CheckFailed(f"{label}: fake gh did not preserve its failure result", stderr)
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
