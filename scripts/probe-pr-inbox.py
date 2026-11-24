#!/usr/bin/env python3
"""Prove live inbox delivery and actual transient host restart without a PR.

Only a disposable user service is started. It runs a local scripted provider,
an isolated Omp home and this repository's inbox bridge; no credentials or
GitHub requests are used. Nothing is installed or enabled for login/boot.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("pr_inbox", ROOT / "scripts/pr-inbox.py")
INBOX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INBOX)
HOST_SPEC = importlib.util.spec_from_file_location("pr_inbox_host", ROOT / "scripts/pr-inbox-host.py")
HOST = importlib.util.module_from_spec(HOST_SPEC)
HOST_SPEC.loader.exec_module(HOST)
IDENTITY = "isolated.example/fixture/project/7"
REQUESTS = []


class Provider(BaseHTTPRequestHandler):
    """Acknowledge actual delivery tokens through the real Omp tool channel."""

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = body.get("messages", [])
        latest = max((i for i, message in enumerate(messages) if message.get("role") == "user"), default=-1)
        content = messages[latest].get("content", "") if latest >= 0 else ""
        text = content if isinstance(content, str) else "\n".join(p.get("text", "") for p in content)
        token = re.search(r"DAILY_DRIVER_PR_DELIVERY (\S+) (\d+) (\d+) (\S+)", text)
        REQUESTS.append({"model": body.get("model"), "generation": int(token[2]) if token else None})
        replied = any(message.get("role") == "tool" for message in messages[latest + 1:])
        # Lose the first generation-1 receipt deliberately, so the actual
        # extension must redeliver it after the durable retry deadline.
        dropped = token and token[2] == "1" and sum(item["generation"] == 1 for item in REQUESTS) == 1
        if token and not replied and not dropped:
            parameters = {"identity": token[1], "generation": int(token[2]), "fence": int(token[3]), "admission": token[4]}
            message = {"role": "assistant", "tool_calls": [{"index": 0, "id": "inbox-receipt",
                "type": "function", "function": {"name": "daily_driver_pr_inbox_receipt", "arguments": json.dumps(parameters)}}]}
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": "INBOX_PROOF_COMPLETE"}
            finish = "stop"
        chunks = [
            {"id": "inbox-proof", "object": "chat.completion.chunk", "model": "proof",
             "choices": [{"index": 0, "delta": message}]},
            {"id": "inbox-proof", "object": "chat.completion.chunk", "model": "proof",
             "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ]
        payload = ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class Rpc:
    """Control only an owned isolated RPC subprocess with bounded frame reads."""

    def __init__(self, base, env):
        self.errors = (base / "seed.stderr").open("w+")
        self.process = subprocess.Popen([shutil.which("omp"), "--mode", "rpc", "--no-extensions",
            "--no-skills", "--no-rules", "--no-context-files", "--no-title", "--tools", "read",
            "--extension", str(ROOT / "extensions/pr-supervision-inbox.mjs"),
            "--session-dir", str(base / "sessions"), "--model", "cold-proof/proof"],
            cwd=base / "sandbox", env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.errors, text=True, bufsize=1)
        self.frames = queue.Queue()

        def collect():
            for line in self.process.stdout:
                try:
                    self.frames.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
            self.frames.put(None)
        threading.Thread(target=collect, daemon=True).start()
        self.until(lambda f: f.get("type") == "ready")

    def send(self, command):
        """Write one supported RPC command to this process's own input."""
        self.process.stdin.write(json.dumps(command) + "\n")
        self.process.stdin.flush()

    def until(self, predicate):
        """Fail on actual extension errors or a bounded observation deadline."""
        deadline = time.monotonic() + 30
        seen = []
        while time.monotonic() < deadline:
            try:
                frame = self.frames.get(timeout=max(0.01, deadline - time.monotonic()))
            except queue.Empty:
                break
            seen.append(frame)
            if frame is None or frame.get("type") == "extension_error":
                break
            if predicate(frame):
                return frame
        self.errors.seek(0)
        raise AssertionError(f"Inbox RPC proof failed: {seen}; {self.errors.read()}")

    def terminal(self):
        """Observe an actual terminal run, not prompt scheduling acceptance."""
        return self.until(lambda f: f.get("type") == "agent_end" and f.get("isTerminal") is not False)

    def close(self):
        """Gracefully dispose the isolated session and its managed inbox timer."""
        self.process.stdin.close()
        try:
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.errors.close()


def worker(base):
    """Run under an actual restarting transient user service, with durable phase."""
    phase_path = base / "phase.json"
    phase = json.loads(phase_path.read_text())
    inbox = INBOX.Inbox(base / "inbox.sqlite")
    try:
        result = HOST.pass_once(inbox, shutil.which("omp"))
        assert result == [{"session": phase["session"], "outcome": "received"}], result
        row = inbox.get(IDENTITY)
        assert row["status"] == "received" and row["generation"] == phase["generation"], row
        if phase["generation"] == 2:
            inbox.enqueue(IDENTITY, phase["session"], 3, {"issue": "isolated fixture", "action": "receipt"})
            phase_path.write_text(json.dumps({"session": phase["session"], "generation": 3, "starts": 1}))
            return 75  # systemd, not this Python controller, starts the next host.
        assert phase["generation"] == 3 and phase["starts"] == 1, phase
        inbox.enqueue(IDENTITY, phase["session"], 3, {"duplicate": True})
        inbox.enqueue(IDENTITY, phase["session"], 2, {"out_of_order": True})
        assert inbox.get(IDENTITY)["status"] == "received"
        inbox.enqueue(IDENTITY, phase["session"], 4, {"action": "must not run"})
        inbox.stop(IDENTITY)
        assert HOST.pass_once(inbox, shutil.which("omp")) == []
        (base / "result.json").write_text(json.dumps({"host_starts": 2, "cold_generations_received": [2, 3],
            "duplicate_and_out_of_order": "coalesced", "stopped_generation": 4}))
        return 0
    finally:
        inbox.close()


def main():
    """Run a bounded host/bridge capability proof with no live installation."""
    if len(sys.argv) == 3 and sys.argv[1] == "--worker":
        raise SystemExit(worker(Path(sys.argv[2])))
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="pr-inbox-proof-") as temporary:
            base = Path(temporary)
            home = base / "home"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            (base / "sandbox").mkdir()
            (agent / "config.yml").write_text("model: cold-proof/proof\n")
            (agent / "models.yml").write_text("providers:\n  cold-proof:\n"
                f"    baseUrl: http://127.0.0.1:{server.server_address[1]}/v1\n"
                "    api: openai-completions\n    apiKey: isolated-proof\n    models:\n"
                "      - id: proof\n        name: Inbox proof\n        api: openai-completions\n"
                "        contextWindow: 131072\n        maxTokens: 1024\n"
                "        cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}\n")
            env = {key: os.environ[key] for key in ("PATH", "LANG", "TERM", "TMPDIR", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS") if key in os.environ}
            env.update(HOME=str(home), DAILY_DRIVER_PR_INBOX=str(base / "inbox.sqlite"))
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
                env[key] = str(home / key.lower())
            inbox = INBOX.Inbox(base / "inbox.sqlite")
            try:
                rpc = Rpc(base, env)
                try:
                    rpc.send({"id": "seed", "type": "prompt", "message": "Persist the isolated owner context."})
                    rpc.terminal()
                    owner = inbox.db.execute("SELECT * FROM owners").fetchone()
                    assert owner, "inbox did not register the actual bound owner"
                    session = owner["session"]
                    inbox.enqueue(IDENTITY, session, 1, {"issue": "isolated fixture", "action": "receipt"})
                    live = HOST.pass_once(inbox, shutil.which("omp"))
                    assert live == [{"session": session, "outcome": "live-extension-owner"}], live
                    rpc.terminal()
                    assert inbox.get(IDENTITY)["status"] == "admitted"
                    rpc.terminal()
                    assert inbox.get(IDENTITY)["status"] == "received"
                    assert inbox.get(IDENTITY)["attempts"] == 2
                finally:
                    rpc.close()
                inbox.enqueue(IDENTITY, session, 2, {"issue": "isolated fixture", "action": "receipt"})
                (base / "phase.json").write_text(json.dumps({"session": session, "generation": 2}))
                unit = "daily-driver-inbox-proof-" + uuid.uuid4().hex
                command = ["systemd-run", "--user", "--wait", "--collect", "--unit", unit,
                    "--property=Restart=on-failure", "--property=RestartSec=100ms",
                    "--property=RuntimeMaxSec=90", "--property=TimeoutStopSec=5",
                    "--property=StartLimitBurst=2", "--property=StartLimitIntervalSec=120",
                    "--working-directory", str(base / "sandbox")]
                for key, value in env.items():
                    command += ["--setenv", f"{key}={value}"]
                command += [sys.executable, str(Path(__file__).resolve()), "--worker", str(base)]
                try:
                    result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                    assert result.returncode == 0, result.stdout + result.stderr
                except BaseException:
                    subprocess.run(["systemctl", "--user", "stop", unit], check=False,
                                   capture_output=True, timeout=15)
                    raise
                summary = json.loads((base / "result.json").read_text())
                assert not any(item["generation"] == 4 for item in REQUESTS), REQUESTS
                summary.update({"live_owner_generation_received": 1, "lost_receipt_delivery_attempts": 2,
                    "external_requests": 0,
                    "provider_models": sorted({item["model"] for item in REQUESTS}),
                    "active_pr_supervision": "not implemented by receipt transport"})
                print(json.dumps(summary, indent=2))
            finally:
                inbox.close()
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
