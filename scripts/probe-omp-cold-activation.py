#!/usr/bin/env python3
"""Measure real Omp cold resumption without credentials, GitHub, or a live PR.

This is a manual capability proof, not a new recurring CI check. The controller
starts and terminates isolated Omp RPC processes. It does not establish an
installed lifecycle host or delivery to an already-running owner.
"""
from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Provider(BaseHTTPRequestHandler):
    """Return a local acknowledgment request, then a terminal response."""

    requests = 0

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        type(self).requests += 1
        messages = body.get("messages", [])
        latest_user = max((i for i, m in enumerate(messages) if m.get("role") == "user"), default=-1)
        acknowledged = any(m.get("role") == "tool" for m in messages[latest_user + 1:])
        if acknowledged:
            message = {"role": "assistant", "content": "COLD_ACTIVATION_ACKNOWLEDGED"}
            finish = "stop"
        else:
            message = {"role": "assistant", "tool_calls": [{"index": 0, "id": "ack-proof",
                "type": "function", "function": {"name": "proof_ack", "arguments": "{}"}}]}
            finish = "tool_calls"
        chunks = [
            {"id": "proof", "object": "chat.completion.chunk", "model": "proof",
             "choices": [{"index": 0, "delta": message}]},
            {"id": "proof", "object": "chat.completion.chunk", "model": "proof",
             "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
             "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ]
        payload = ("".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def run_process(omp, base, env, session=None):
    """Observe one actual process through persisted tool acknowledgment."""
    argv = [omp, "--mode", "rpc", "--no-extensions", "--no-skills", "--no-rules",
            "--no-context-files", "--no-title", "--tools", "read", "--extension", str(base / "proof.mjs"),
            "--session-dir", str(base / "sessions"), "--model", "cold-proof/proof"]
    if session:
        argv += ["--resume", str(session)]
    with (base / ("resume.stderr" if session else "first.stderr")).open("w+") as errors:
        process = subprocess.Popen(argv, cwd=base / "sandbox", env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=errors, text=True, bufsize=1)
        frames = queue.Queue()

        def collect():
            for line in process.stdout:
                try:
                    frames.put(json.loads(line))
                except json.JSONDecodeError:
                    continue
            frames.put(None)

        threading.Thread(target=collect, daemon=True).start()
        deadline = time.monotonic() + 60
        observed = []

        def until(predicate):
            while time.monotonic() < deadline:
                try:
                    frame = frames.get(timeout=max(0.01, deadline - time.monotonic()))
                except queue.Empty:
                    break
                observed.append(frame)
                if frame is None:
                    break
                if predicate(frame):
                    return frame
            errors.seek(0)
            raise AssertionError(f"RPC proof failed: {observed}; {errors.read()}")

        try:
            until(lambda f: f.get("type") == "ready")
            process.stdin.write(json.dumps({"id": "delivery", "type": "prompt", "message":
                "Read the supplied cold proof context and acknowledge this delivery with proof_ack."}) + "\n")
            process.stdin.flush()
            until(lambda f: f.get("type") == "tool_execution_end" and f.get("toolName") == "proof_ack"
                  and not f.get("isError"))
            until(lambda f: f.get("type") == "agent_end" and f.get("isTerminal") is not False)
            files = list((base / "sessions").glob("*.jsonl"))
            assert len(files) == 1, files
            contents = files[0].read_text()
            acknowledgments = [json.loads(line) for line in contents.splitlines()
                               if json.loads(line).get("customType") == "cold-proof-ack"]
            assert acknowledgments, contents
            session_id = next(json.loads(line)["id"] for line in contents.splitlines()
                              if json.loads(line).get("type") == "session")
            lease = subprocess.run([omp, "session", "lease", "--json", "--", session_id],
                cwd=base / "sandbox", env=env, check=True, capture_output=True, text=True, timeout=15)
            assert json.loads(lease.stdout) == {"held": [session_id], "unknown": []}, lease.stdout
            return files[0], len(acknowledgments)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def main():
    """Prove only capabilities this local isolated controller exercises."""
    omp = shutil.which("omp")
    if not omp:
        raise RuntimeError("omp is required")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="omp-cold-proof-") as temporary:
            base = Path(temporary)
            home = base / "home"
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            (base / "sandbox").mkdir()
            (agent / "config.yml").write_text("model: cold-proof/proof\n")
            (agent / "models.yml").write_text(
                "providers:\n  cold-proof:\n"
                f"    baseUrl: http://127.0.0.1:{server.server_address[1]}/v1\n"
                "    api: openai-completions\n    apiKey: isolated-proof\n    models:\n"
                "      - id: proof\n        name: Cold proof\n        api: openai-completions\n"
                "        contextWindow: 131072\n        maxTokens: 1024\n"
                "        cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}\n")
            (base / "proof.mjs").write_text('''import { z } from "@oh-my-pi/pi-coding-agent";
export default function(pi) {
 pi.registerTool({name:"proof_ack",label:"Proof acknowledgment",description:"Persist the isolated delivery acknowledgment",
  parameters:z.object({}),execute:async () => {
   pi.appendEntry("cold-proof-ack", {acknowledged:true});
   return {content:[{type:"text",text:"acknowledged"}],details:{acknowledged:true}};
  }});
}
''')
            env = {key: os.environ[key] for key in ("PATH", "LANG", "TERM", "TMPDIR") if key in os.environ}
            env["HOME"] = str(home)
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
                env[key] = str(home / key.lower())
            session, first = run_process(omp, base, env)
            _, second = run_process(omp, base, env, session)
            assert first == 1 and second == 2, (first, second)
            print(json.dumps({"cold_cli_resume": "proved", "persisted_acknowledgments": second,
                "processes": 2, "external_requests": 0, "local_provider_requests": Provider.requests,
                "host_restart_recovery": "not proved", "live_owner_reattachment": "not proved",
                "limit": "This controller starts Omp; no installed lifecycle host restarts the controller or routes durable deliveries to a live owner."}, indent=2))
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
