#!/usr/bin/env python3
"""Exercise live Omp undertaking routing against an offline provider.

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
REVIEWER_MODEL = "independent-reviewer"
REVIEWER_REQUESTS: list[str] = []
TOTAL_REQUESTS = 0
REQUEST_IDENTITIES: list[str] = []
PROBES = {
    "routing": "Exercise smoke-routing with the offline reviewer.",
    "reviewer": "ROUTE_REVIEW_CHILD",
    "boundaries": "Exercise offline undertaking request boundaries.",
    "model_check": "What is 17 times 23? Answer with only the number.",
}


class Model(BaseHTTPRequestHandler):
    """Respond to routing probes without an external model."""

    def log_message(self, *_args) -> None:
        pass

    def do_POST(self) -> None:
        global TOTAL_REQUESTS
        TOTAL_REQUESTS += 1
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUEST_IDENTITIES.append(body["model"])
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
                    ("daily_driver_route_undertaking", {"issue": 819, "modelClass": "routine"}) if index == 1 else
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
        elif phase == "model_check":
            message = {"role": "assistant", "content": "391"}
            finish = "stop"
        elif phase == "boundaries":
            message = {"role": "assistant", "content": "BOUNDARY_OK"}
            finish = "stop"
        elif phase == "routing":
            message = {"role": "assistant", "content": "Routing fixture complete."}
            finish = "stop"
        else:
            raise AssertionError(f"Unexpected probe phase: {phase}")
        if phase == "boundaries":
            chunks = [
                {"type": "message_start", "message": {"id": "task-state", "type": "message",
                 "role": "assistant", "model": body["model"], "content": [], "stop_reason": None,
                 "usage": {"input_tokens": 20, "output_tokens": 0}}},
                {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}},
                {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": "BOUNDARY_OK"}},
                {"type": "content_block_stop", "index": 0},
                {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                 "usage": {"output_tokens": 5}},
                {"type": "message_stop"},
            ]
            payload = "".join(f"event: {chunk['type']}\ndata: {json.dumps(chunk)}\n\n" for chunk in chunks)
        elif not body.get("stream", False):
            payload = json.dumps({"id": "routing", "object": "chat.completion", "model": body["model"],
                                  "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                                  "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25}})
        else:
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
        self.send_header("Content-Type", "text/event-stream" if body.get("stream", False) else "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_routing_controls(omp: str, base: Path, env: dict[str, str]) -> None:
    """Keep cancellation and malformed-state controls available without inference."""
    observer = base / "controls-observer.mjs"
    observer.write_text('''import { createHash } from "node:crypto";
export default function(pi) {
 pi.registerCommand("seed-controls", {handler: async (args,ctx) => {
  const model = ctx.models.current();
  const auth = ctx.modelRegistry.authStorage.keys.source(model.provider, {env:"aliases"});
  const data = args === "malformed" ? {schema:1,issue:828} : {
   schema:1,issue:828,modelClass:"routine",
   selectedModel: model.provider + "/independent-reviewer", selectedEffort:pi.getThinkingLevel(),
   origin:{provider:model.provider,model:model.id,api:model.api,baseUrl:model.baseUrl,
    headersDigest:createHash("sha256").update(JSON.stringify(Object.entries(model.headers ?? {}).sort())).digest("hex")},
   authenticationRoute:auth.kind === "env" ? "env:" + auth.envVar : auth.kind
  };
  await ctx.newSession({setup:async manager => {
   manager.appendMessage({role:"user",content:[{type:"text",text:"CONTROL_CONVERSATION_RETAINED"}],timestamp:Date.now()});
   manager.appendCustomEntry("daily-driver-undertaking-route",data);
   await manager.ensureOnDisk();
  }});
  await ctx.reload();
 }});
}''', encoding="utf-8")
    requests_before = TOTAL_REQUESTS
    for malformed in (False, True):
        storage = base / ("controls-malformed-session" if malformed else "controls-rejected-session")
        storage.mkdir()
        for resume in (False, True):
            session_file = next(storage.glob("*.jsonl")) if resume else None
            argv = [omp, "--mode", "rpc", "--extension", str(ROOT / "extensions/daily-driver.js"),
                    "--extension", str(observer), "--session-dir", str(storage), "--tools", "read,write"]
            if session_file:
                argv.extend(["--resume", str(session_file)])
            stderr_path = base / f"controls-{malformed}-{resume}.stderr"
            with stderr_path.open("w", encoding="utf-8") as stderr:
                process = subprocess.Popen(argv, cwd=base / "sandbox", env=env, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
                frames: queue.Queue = queue.Queue()
                threading.Thread(target=FIXTURE.read_frames, args=(process.stdout, frames), daemon=True).start()
                captured = []
                deadline = time.monotonic() + 60

                def wait(predicate):
                    while time.monotonic() < deadline:
                        try:
                            frame = frames.get(timeout=max(0.1, deadline - time.monotonic()))
                        except queue.Empty:
                            break
                        if frame is None:
                            raise AssertionError(f"Control session exited: {stderr_path.read_text()}")
                        captured.append(frame)
                        if predicate(frame):
                            return frame
                    raise AssertionError(f"Control deadline: {captured}; {stderr_path.read_text()}")

                def send(value):
                    process.stdin.write(json.dumps(value) + "\n")
                    process.stdin.flush()

                def command(identifier, text):
                    start = len(captured)
                    send({"id": identifier, "type": "prompt", "message": text})
                    result = wait(lambda frame: frame.get("type") == "response" and frame.get("id") == identifier)
                    assert result.get("success"), result
                    settled = wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == identifier)
                    assert settled.get("status") == "completed" and not settled.get("agentInvoked"), settled
                    return captured[start:]

                def status(identifier):
                    output = command(identifier, "/undertaking status")
                    messages = [frame.get("message", "") for frame in output]
                    return next(json.loads(message) for message in messages if message.startswith("{") and '"cancelOwner"' in message)

                try:
                    wait(lambda frame: frame.get("type") == "ready")
                    send({"id": "controls-model", "type": "set_model", "provider": FIXTURE.PROVIDER, "modelId": FIXTURE.MODEL})
                    assert wait(lambda frame: frame.get("id") == "controls-model").get("success")
                    if resume:
                        assert status("resumed-status")["state"] == "cancelled"
                        command("repeat-cancel", "/undertaking cancel 828")
                    else:
                        command("seed", "/seed-controls " + ("malformed" if malformed else "active"))
                        seeded = status("seeded-status")
                        assert seeded["state"] == ("blocked" if malformed else "selected"), seeded
                        info = status("owner-status")
                        assert info["issue"] == 828, info
                        assert info["state"] == ("blocked" if malformed else "selected"), info
                        assert info["observedModel"] == "unreported", info
                        if malformed:
                            assert info["lastRejection"], info
                        command("wrong-owner", "/undertaking cancel 829")
                        assert status("still-owned")["issue"] == 828
                        command("cancel-owner", "/undertaking cancel 828")
                        assert status("cancelled-status")["state"] == "cancelled"
                    assert TOTAL_REQUESTS == requests_before, "local recovery must never reach inference"
                    assert not any(frame.get("type") == "tool_execution_start" for frame in captured), captured
                finally:
                    process.stdin.close()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            session_file = next(storage.glob("*.jsonl"))
            entries = [json.loads(line) for line in session_file.read_text().splitlines()]
            routes = [entry["data"] for entry in entries if entry.get("customType") == "daily-driver-undertaking-route"]
            assert routes[-1] == {"schema": 2, "issue": 828, "lifecycle": "cancelled"}, routes
            assert not any(route.get("completed") or route.get("lifecycle") == "completed" for route in routes)
            if not malformed:
                assert "CONTROL_CONVERSATION_RETAINED" in session_file.read_text()
    print("Local undertaking controls: malformed state, exact owner and cancellation reload passed with zero inference requests")


def run_routing_boundaries(omp: str, base: Path, env: dict[str, str]) -> None:
    """Exercise operator model changes after initial routing and after resume."""
    observer = base / "boundaries-observer.mjs"
    observer.write_text('''import { installUndertakingRouting } from "''' + os.path.relpath(ROOT / "extensions/undertaking-routing.mjs", base) + '''";
export default function(pi) {
 const endpoint=process.env.OFFLINE_PROVIDER_URL;
 const modelConfig=id=>({id,name:id,reasoning:true,input:["text"],compat:{kimiApiFormat:"anthropic"},
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0},contextWindow:131072,maxTokens:1024});
 pi.registerProvider("kimi-code",{
  baseUrl:endpoint,apiKey:"offline-routing-fixture",api:"openai-completions",
  models:[modelConfig("embark-title-probe-model"),modelConfig("independent-reviewer")]
 });
 let route;
 const routes = [{
  referenceModel:"kimi-code/embark-title-probe-model",
  classes:{complex:"kimi-code/independent-reviewer"}
 }];
 const register = pi.registerTool.bind(pi);
 pi.registerTool = definition => {
  if (definition.name === "daily_driver_route_undertaking") route = definition;
  register(definition);
 };
 installUndertakingRouting(pi, () => pi.pi.settings, () => routes);
 pi.registerCommand("route-boundary", {handler:async(_args,ctx)=>{
  const result=await route.execute("boundary",{issue:829,modelClass:"complex"},null,null,ctx);
  ctx.ui.notify(JSON.stringify({admission:result}),"info");
 }});
}''', encoding="utf-8")
    storage = base / "boundaries-session"
    storage.mkdir()
    start_requests = len(REQUEST_IDENTITIES)
    selected = f"kimi-code/{REVIEWER_MODEL}"
    for resume in (False, True):
        session_file = next(storage.glob("*.jsonl")) if resume else None
        argv = [omp, "--mode", "rpc", "--extension", str(observer),
                "--session-dir", str(storage), "--tools", "read"]
        if session_file:
            argv.extend(["--resume", str(session_file)])
        with (base / f"boundaries-{resume}.stderr").open("w", encoding="utf-8") as stderr:
            process = subprocess.Popen(argv, cwd=base / "sandbox", env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
            frames: queue.Queue = queue.Queue()
            threading.Thread(target=FIXTURE.read_frames, args=(process.stdout, frames), daemon=True).start()
            captured = []
            deadline = time.monotonic() + 90

            def wait(predicate):
                while time.monotonic() < deadline:
                    frame = frames.get(timeout=max(0.1, deadline - time.monotonic()))
                    if frame is None:
                        raise AssertionError(f"Boundary session exited; {captured}")
                    captured.append(frame)
                    if predicate(frame):
                        return frame
                raise AssertionError(f"Boundary deadline; {captured}")

            def send(value):
                process.stdin.write(json.dumps(value) + "\n")
                process.stdin.flush()

            def command(identifier, text):
                offset = len(captured)
                send({"id": identifier, "type": "prompt", "message": text})
                result = wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == identifier)
                assert result.get("status") == "completed" and not result.get("agentInvoked"), result
                return captured[offset:]

            def status(identifier):
                output = command(identifier, "/undertaking status")
                return next(json.loads(frame["message"]) for frame in output
                            if frame.get("message", "").startswith("{") and '"cancelOwner"' in frame["message"])

            def prompt(identifier):
                send({"id": identifier, "type": "prompt", "message": PROBES["boundaries"]})
                return wait(lambda frame: frame.get("type") == "prompt_result" and frame.get("id") == identifier)

            def model(identifier, model_id):
                send({"id": identifier, "type": "set_model", "provider": "kimi-code", "modelId": model_id})
                assert wait(lambda frame: frame.get("id") == identifier).get("success")

            try:
                wait(lambda frame: frame.get("type") == "ready")
                if not resume:
                    model("initial-model", FIXTURE.MODEL)
                    output = command("admit", "/route-boundary")
                    admission = next(json.loads(frame["message"])["admission"] for frame in output
                                     if frame.get("message", "").startswith('{"admission":'))
                    assert not admission.get("isError"), admission
                    assert admission["details"]["undertaking"]["selectedModel"] == selected, admission
                    model("operator-model", FIXTURE.MODEL)
                    send({"id": "operator-effort", "type": "set_thinking_level", "level": "low"})
                    effort = wait(lambda frame: frame.get("id") == "operator-effort")
                    assert effort.get("success"), effort
                before = len(REQUEST_IDENTITIES)
                result = prompt("operator-prompt")
                assert result.get("status") == "completed", result
                assert len(REQUEST_IDENTITIES) == before + 1, "operator-selected request did not reach provider"
                assert REQUEST_IDENTITIES[-1] == FIXTURE.MODEL, REQUEST_IDENTITIES
                info = status("operator-status")
                assert info["hostModel"] == f"kimi-code/{FIXTURE.MODEL}", info
                assert info["hostEffort"] == "low", info
                assert info["issue"] == 829, info
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    assert REQUEST_IDENTITIES[start_requests:] == [FIXTURE.MODEL, FIXTURE.MODEL], REQUEST_IDENTITIES[start_requests:]
    print("Undertaking admission: operator model and effort reached local provider before and after resume")


def run(omp: str, base: Path, env: dict[str, str], observer: Path) -> list[dict]:
    """Exercise routing and reviewer dispatch in a real RPC session."""
    storage = base / "routing-session"
    storage.mkdir(exist_ok=True)
    stderr_path = base / "routing.stderr"
    argv = [omp, "--mode", "rpc", "--extension", str(ROOT / "extensions/daily-driver.js"),
            "--extension", str(observer), "--session-dir", str(storage), "--tools", "read,write,task,wait"]
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
            send({"id": "prompt", "type": "prompt", "message": PROBES["routing"]})
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
        raise RuntimeError("omp must be installed for the undertaking routing check")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Model)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="check-omp-routing-") as temporary:
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
  for (const value of [[], [{referenceModel:"fixture/model",classes:{routine:"fixture/worker"}}]]) {
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
            env = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "TERM") if key in os.environ}
            env.update(HOME=str(home))
            env["OFFLINE_PROVIDER_URL"] = f"http://127.0.0.1:{server.server_address[1]}/v1"
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
                env[key] = str(home / key.lower())
            agents = home / ".omp" / "agent" / "agents"
            agents.mkdir(exist_ok=True)
            (agents / "reviewer.md").write_text(
                "---\nname: reviewer\ndescription: Offline routing regression\n"
                f"model: {FIXTURE.PROVIDER}/{REVIEWER_MODEL}\n---\nReturn ROUTE_REVIEW_OK without tools.\n",
                encoding="utf-8",
            )
            if sys.argv[1:] == ["--routing-boundaries-only"]:
                run_routing_boundaries(omp, base, env)
                return
            routing = run(omp, base, env, routing_observer)
            route_calls = [frame for frame in routing if frame.get("type") == "tool_execution_end"]
            assert len(route_calls) == 5 and all(not frame.get("isError") for frame in route_calls), route_calls
            assert "verified" in json.dumps(route_calls[1]), route_calls[1]
            assert "ROUTE_REVIEW_OK" in json.dumps(route_calls[3]), route_calls[3]
            assert REQUESTS["reviewer"] == 1, REQUESTS
            assert REVIEWER_REQUESTS == [REVIEWER_MODEL], REVIEWER_REQUESTS
            print("Default class routes: real settings clones and verified-undertaking reviewer dispatch passed")
            run_routing_controls(omp, base, env)
            run_routing_boundaries(omp, base, env)
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
