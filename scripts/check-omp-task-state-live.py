#!/usr/bin/env python3
"""Prevent mock-only stop enforcement from hiding real Omp resume or abort defects.

The installed Omp loads the shipped extension against a local scripted provider.
No external model or service is used. All session files stay in a disposable home.
"""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("omp_live_fixture", ROOT / "scripts/check-omp-embark-title-live.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
REQUESTS: dict[str, int] = {}
SOURCES: dict[str, dict] = {}
REVIEWER_MODEL = "independent-reviewer"
REVIEWER_REQUESTS: list[str] = []
PROBES = {
    "first": "Fix smoke-first. Verify the fixture offline only.",
    "resume": "Report smoke-resume current state without starting a new task.",
    "cancel": "Fix smoke-cancel abort fixture.",
    "contract": "Fix smoke-contract. Verify the fixture offline only.",
    "routing": "Exercise smoke-routing with the offline reviewer.",
    "reviewer": "ROUTE_REVIEW_CHILD",
}


class Model(BaseHTTPRequestHandler):
    """Force unsupported stops instead of depending on a model's voluntary compliance."""

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        messages = body.get("messages", [])
        phase = None
        for candidate in reversed(messages):
            if candidate.get("role") == "system":
                continue
            content = candidate.get("content")
            parts = [part.get("text", "") for part in content if isinstance(part, dict)] if isinstance(content, list) else [content or ""]
            lines = [line.strip().removeprefix("User:").strip()
                     for part in parts for line in part.splitlines()]
            phase = next((name for name, prompt in PROBES.items() if prompt in lines), None)
            if phase is not None:
                break
        if phase is None:
            raise AssertionError(f"No external probe phrase in provider messages: {repr(messages[-5:])[:16000]}")
        index = REQUESTS.get(phase, 0)
        if phase == "routing" and index < 5:
            if index == 3:
                name, args = "wait", {"i": "Waiting for offline reviewer"}
            elif index == 2:
                name, args = "task", {
                    "tasks": [{"agent": "reviewer", "name": "RouteProbe", "task": PROBES["reviewer"],
                               "solutionSpace": "Review the isolated routing fixture."}],
                    "context": "Offline routing regression. Return ROUTE_REVIEW_OK without tools.",
                    "i": "Dispatching offline reviewer",
                }
            else:
                tool, params = (
                    ("daily_driver_set_session_title", {"title": "#819 Reviewer routing fixture"}) if index == 0 else
                    ("daily_driver_route_undertaking", {"issue": 819, "modelClass": "implementation"}) if index == 1 else
                    ("daily_driver_finish_undertaking", {"issue": 819})
                )
                name, args = "write", {"path": f"xd://{tool}", "content": json.dumps(params)}
            message = {"role": "assistant", "tool_calls": [{
                "index": 0, "id": f"routing-{index}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }]}
            finish = "tool_calls"
        elif phase == "reviewer":
            REVIEWER_REQUESTS.append(body["model"])
            message = {"role": "assistant", "content": "ROUTE_REVIEW_OK"}
            finish = "stop"
        elif phase == "contract" and index < 10:
            def latest_status() -> dict:
                decoder = json.JSONDecoder()
                for candidate in reversed(messages):
                    content = FIXTURE.text_of(candidate.get("content"))
                    offset = content.find('{"state":')
                    if offset >= 0:
                        try:
                            result, _end = decoder.raw_decode(content, offset)
                            return result
                        except json.JSONDecodeError:
                            pass
                raise AssertionError("Task-state status was not returned")

            if index == 0:
                name, args = "read", {"path": "xd://daily_driver_task_state"}
            elif index == 5:
                name, args = "read", {"path": "absent-task-state-fixture"}
            else:
                name = "write"
                if index in (1, 6):
                    params = {"action": "status"}
                elif index == 2:
                    source = next(item for item in latest_status()["sources"] if item["kind"] == "user")
                    SOURCES[phase] = source
                    params = {"action": "status", "record": json.dumps({"sourceId": source["sourceId"]})}
                elif index == 3:
                    source = SOURCES[phase]
                    ref = {"sourceId": source["sourceId"], "quote": "Verify the fixture offline only."}
                    params = {"action": "begin", "record": json.dumps({
                        "taskId": "fixture", "operation": "verify", "target": "fixture", "source": ref,
                    })}
                elif index == 4:
                    source = SOURCES[phase]
                    params = {"action": "authorization", "record": json.dumps({
                        "id": "fixture-approval", "kind": "user", "operation": "verify", "target": "fixture",
                        "source": {"sourceId": source["sourceId"], "quote": "Verify the fixture offline only."},
                        "limits": "offline only", "conditions": "fixture only",
                    })}
                elif index == 7:
                    evidence = next(item for item in latest_status()["evidence"] if item["isError"])
                    SOURCES["failure"] = evidence
                    params = {"action": "status", "record": json.dumps({"sourceId": evidence["sourceId"]})}
                elif index == 8:
                    # Quote the entry retrieved by sourceId, not the status excerpt, as the device documents.
                    evidence = latest_status()["source"]
                    assert evidence["sourceId"] == SOURCES["failure"]["sourceId"], evidence
                    ref = {"sourceId": evidence["sourceId"], "quote": evidence["text"]}
                    params = {"action": "blocker", "record": json.dumps({
                        "kind": "execution", "operation": "verify", "target": "fixture",
                        "evidence": [ref], "authorizationIds": ["fixture-approval"],
                        "routes": [{"route": "fixture", "disposition": "failed", "evidence": ref}],
                        "independentWork": {"pending": [], "completed": []},
                        "externalContribution": "Provide fixture access.", "resume": "Retry the fixture.",
                    })}
                else:
                    params = {"action": "complete", "record": json.dumps({"summary": "Fixture work completed."})}
                args = {"path": "xd://daily_driver_task_state", "content": json.dumps(params)}
            message = {"role": "assistant", "tool_calls": [{
                "index": 0, "id": f"contract-{index}", "type": "function",
                "function": {"name": name, "arguments": json.dumps(args)},
            }]}
            finish = "tool_calls"
        elif phase == "first" and index < 3:
            if index == 0:
                params = {"action": "status"}
            elif index == 1:
                status = None
                decoder = json.JSONDecoder()
                for candidate in reversed(messages):
                    content = FIXTURE.text_of(candidate.get("content"))
                    offset = content.find('{"state":')
                    if offset < 0:
                        continue
                    try:
                        decoded, _end = decoder.raw_decode(content, offset)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(decoded, dict) and isinstance(decoded.get("sources"), list):
                        status = decoded
                        break
                if status is None:
                    raise AssertionError(f"No task-state status output in provider messages: {repr(messages[-5:])[:16000]}")
                source = next(item for item in status["sources"] if item["kind"] == "user")
                SOURCES[phase] = source
                params = {"action": "begin", "record": json.dumps({"taskId": "fixture", "operation": "verify", "target": "fixture"})}
            else:
                source = SOURCES[phase]
                params = {"action": "authorization", "record": json.dumps({
                    "id": "offline-fixture", "kind": "user", "operation": "verify", "target": "fixture",
                    "source": {"sourceId": source["sourceId"], "quote": "Verify the fixture offline only."},
                    "limits": "offline only", "conditions": "fixture only",
                })}
            message = {"role": "assistant", "tool_calls": [{
                "index": 0, "id": f"state-{index}", "type": "function",
                "function": {"name": "write", "arguments": json.dumps({
                    "path": "xd://daily_driver_task_state", "content": json.dumps(params),
                })},
            }]}
            finish = "tool_calls"
        else:
            message = {"role": "assistant", "content": "I stopped without evidence or reported completion."}
            finish = "stop"
        chunks = [
            {"id": "task-state", "object": "chat.completion.chunk", "model": FIXTURE.MODEL,
             "choices": [{"index": 0, "delta": message}]},
            {"id": "task-state", "object": "chat.completion.chunk", "model": FIXTURE.MODEL,
             "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
             "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}},
        ]
        payload = "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"
        data = payload.encode("utf-8")
        REQUESTS[phase] = index + 1
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run(omp: str, base: Path, env: dict[str, str], phase: str, observer: Path) -> list[dict]:
    """Reject lost resume state and corrections delivered after a real RPC abort."""
    storage = base / (f"{phase}-session" if phase in ("cancel", "contract", "routing") else "persistent-session")
    storage.mkdir(exist_ok=True)
    resume = ["--resume", str(next(storage.glob("*.jsonl")))] if phase == "resume" else []
    stderr_path = base / f"{phase}.stderr"
    argv = [omp, "--mode", "rpc", "--extension", str(ROOT / "extensions/daily-driver.js"),
            "--extension", str(observer), "--session-dir", str(storage), *resume, "--tools",
            "read,write,task,wait" if phase == "routing" else "read,write"]
    with stderr_path.open("w", encoding="utf-8") as stderr:
        process = subprocess.Popen(argv, cwd=base / "sandbox", env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
        frames: queue.Queue = queue.Queue()
        threading.Thread(target=FIXTURE.read_frames, args=(process.stdout, frames), daemon=True).start()
        captured = []
        deadline = time.monotonic() + 90

        def send(value: dict) -> None:
            process.stdin.write(json.dumps(value) + "\n")
            process.stdin.flush()

        def wait(predicate):
            while time.monotonic() < deadline:
                try:
                    frame = frames.get(timeout=max(0.1, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if frame is None:
                    raise AssertionError(f"Omp exited: {stderr_path.read_text()}")
                captured.append(frame)
                if frame.get("type") == "extension_error":
                    raise AssertionError(frame)
                if predicate(frame):
                    return frame
            raise AssertionError(f"Omp deadline: {stderr_path.read_text()}")

        try:
            wait(lambda frame: frame.get("type") == "ready")
            send({"id": "model", "type": "set_model", "provider": FIXTURE.PROVIDER, "modelId": FIXTURE.MODEL})
            assert wait(lambda frame: frame.get("id") == "model").get("success")
            prompt = PROBES[phase]
            send({"id": "prompt", "type": "prompt", "message": prompt})
            if phase == "cancel":
                while not (base / "abort-ready").exists():
                    assert time.monotonic() < deadline, stderr_path.read_text()
                    time.sleep(0.02)
                send({"id": "abort", "type": "abort"})
            wait(lambda frame: frame.get("type") == "agent_end" and frame.get("isTerminal", True))
            process.stdin.close()
            process.wait(timeout=10)
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
    return captured


def main() -> None:
    omp = shutil.which("omp")
    if not omp:
        raise RuntimeError("omp must be installed for the task-state lifecycle proof")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Model)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="check-omp-task-state-") as temporary:
            base = Path(temporary)
            home = base / "home"
            (base / "sandbox").mkdir()
            FIXTURE.write_home(home, server.server_address[1])
            models_config = home / ".omp" / "agent" / "models.yml"
            models_config.write_text(models_config.read_text().replace(
                "    auth: none\n", "    apiKey: offline-routing-fixture\n",
            ) + (
                f"      - id: {REVIEWER_MODEL}\n"
                "        name: Independent reviewer\n"
                "        api: openai-completions\n"
                "        contextWindow: 131072\n"
                "        maxTokens: 1024\n"
                "        cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}\n"
            ), encoding="utf-8")
            observer = base / "observer.mjs"
            # Unset route configuration used to poison later settings clones and reviewer dispatch.
            routing_observer = base / "routing-observer.mjs"
            routing_observer.write_text('''import assert from "node:assert/strict";
import { readModelClassRoutes, MODEL_CLASS_ROUTES } from "''' + os.path.relpath(ROOT / "extensions/role-default-helper.mjs", base) + '''";
import { lookup } from "@oh-my-pi/pi-coding-agent/config/registry";
export default function(pi) {
 pi.on("session_start", async (_event, ctx) => {
  const settings = pi.pi.settings;
  assert.deepEqual(await readModelClassRoutes(settings), MODEL_CLASS_ROUTES, "parent defaults");
  const clone = await settings.cloneForCwd(ctx.cwd);
  assert.deepEqual(await readModelClassRoutes(clone), MODEL_CLASS_ROUTES, "cloned defaults");
  const routes = lookup("dailyDriver.modelClassRoutes");
  for (const value of [[], [{referenceModel:"fixture/model",classes:{implementation:"fixture/worker"}}]]) {
   const explicit = settings.overlay();
   routes.override(explicit, value);
   assert.deepEqual(await readModelClassRoutes(await explicit.cloneForCwd(ctx.cwd)), value, "explicit clone");
  }
  for (const value of [null, {}, "invalid", [{referenceModel:"fixture/model",classes:{unknown:"fixture/worker"}}],
    [MODEL_CLASS_ROUTES[0], MODEL_CLASS_ROUTES[0]]]) {
   assert.throws(() => routes.override(settings.overlay(), value));
  }
 });
}''', encoding="utf-8")
            observer.write_text('''import { appendFileSync, writeFileSync } from "node:fs";
export default function(pi) {
 pi.on("session_stop", async (event, ctx) => {
  const entries = ctx.sessionManager.getBranch();
  const state = entries.filter(e => e.type === "custom" && e.customType === "daily-driver.task-state").at(-1)?.data.state;
  const cancel = state?.operation.includes("smoke-cancel");
  appendFileSync(process.env.STATE_LOG, JSON.stringify({corrections:state?.corrections,status:state?.status,cancel})+"\\n");
  if (cancel) {
   writeFileSync(process.env.ABORT_READY, "ready");
   await new Promise(resolve => {
    if(event.signal.aborted) return resolve();
    event.signal.addEventListener("abort",resolve,{once:true});
   });
   const after = ctx.sessionManager.getBranch().filter(e=>e.type === "custom" && e.customType === "daily-driver.task-state").at(-1)?.data.state;
   appendFileSync(process.env.STATE_LOG, JSON.stringify({cancelled:event.signal.aborted,status:after?.status})+"\\n");
  }
 });
}''', encoding="utf-8")
            env = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "TERM") if key in os.environ}
            env.update(HOME=str(home), STATE_LOG=str(base / "state.log"), ABORT_READY=str(base / "abort-ready"))
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
                env[key] = str(home / key.lower())
            agents = home / ".omp" / "agent" / "agents"
            agents.mkdir(exist_ok=True)
            (agents / "reviewer.md").write_text(
                "---\nname: reviewer\ndescription: Offline routing regression\n"
                f"model: {FIXTURE.PROVIDER}/{REVIEWER_MODEL}\n---\nReturn ROUTE_REVIEW_OK without tools.\n",
                encoding="utf-8",
            )
            routing = run(omp, base, env, "routing", routing_observer)
            route_calls = [frame for frame in routing if frame.get("type") == "tool_execution_end"]
            assert len(route_calls) == 5 and all(not frame.get("isError") for frame in route_calls), route_calls
            assert "verified" in json.dumps(route_calls[1]), route_calls[1]
            assert "ROUTE_REVIEW_OK" in json.dumps(route_calls[3]), route_calls[3]
            assert REQUESTS["reviewer"] == 1, REQUESTS
            assert REVIEWER_REQUESTS == [REVIEWER_MODEL], REVIEWER_REQUESTS
            print("Default class routes: real settings clones and verified-undertaking reviewer dispatch passed")
            if sys.argv[1:] == ["--routing-only"]:
                return
            first = run(omp, base, env, "first", observer)
            run(omp, base, env, "resume", observer)
            run(omp, base, env, "cancel", observer)
            # A rendered device and its documented calls must work in the installed runtime, not only in a mock.
            contract = run(omp, base, env, "contract", observer)
            calls = [frame for frame in contract if frame.get("type") == "tool_execution_end"]
            assert len(calls) == 10, calls
            assert all(not frame.get("isError") for index, frame in enumerate(calls) if index != 5), calls
            assert calls[5].get("isError"), calls[5]
            contract_session = next((base / "contract-session").glob("*.jsonl"))
            contract_entries = [json.loads(line) for line in contract_session.read_text().splitlines()]
            contract_state = [entry["data"]["state"] for entry in contract_entries
                              if entry.get("customType") == "daily-driver.task-state"][-1]
            assert contract_state["status"] == "reported-complete", contract_state
            assert contract_state["blocker"]["kind"] == "execution", contract_state
            print("Rendered task-state device:", json.dumps(calls[0]))
            rows = [json.loads(line) for line in (base / "state.log").read_text().splitlines()]
            assert all(row["corrections"] <= 2 for row in rows if "corrections" in row), rows
            # Three state commands and three model stops prove exactly two corrective turns;
            # shutdown may emit extra stop notifications without another model request.
            assert REQUESTS["first"] == 6, REQUESTS
            assert any(row.get("cancelled") and row.get("status") == "cancelled" for row in rows), rows
            assert REQUESTS["cancel"] == 1, REQUESTS
            assert REQUESTS["resume"] == 1, REQUESTS
            results = [frame for frame in first if frame.get("type") == "tool_execution_end"]
            assert len(results) == 3 and all(not frame.get("isError") for frame in results), results
            session = next((base / "persistent-session").glob("*.jsonl"))
            saved = [json.loads(line) for line in session.read_text().splitlines()]
            state = [entry["data"]["state"] for entry in saved if entry.get("customType") == "daily-driver.task-state"][-1]
            assert state["authorizations"][0]["id"] == "offline-fixture", state
            assert state["status"] == "active" and state.get("stopFailure"), state
            print("check-omp-task-state-live: PASS; durable approval, two-correction cap, process resume and RPC abort exercised offline")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
