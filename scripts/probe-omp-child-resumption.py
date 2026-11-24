#!/usr/bin/env python3
"""Measure child ownership across real Omp resume/restore in an isolated home.

A scripted localhost provider creates one bounded child and returns constants.
Only allowlisted session/agent metadata is printed. No credentials or GitHub
access are used, and no live session or PR is touched.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("inbox_probe", ROOT / "scripts/probe-pr-inbox.py")
FIXTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE)
COUNTS = {}


def text(content):
    """Read only synthetic provider input produced by this isolated fixture."""
    return content if isinstance(content, str) else "\n".join(part.get("text", "") for part in content or [] if isinstance(part, dict))


class Provider(BaseHTTPRequestHandler):
    """Drive actual title/task/write calls with a credential-free local model."""

    def log_message(self, *_args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        latest = next((m for m in reversed(body.get("messages", [])) if m.get("role") == "user"), {})
        prompt = text(latest.get("content", ""))
        phase = "spawn" if "SPAWN_CHILD_PROOF" in prompt else "relay" if "ROOT_RELAY_CHILD" in prompt else "child"
        index = COUNTS.get(phase, 0)
        COUNTS[phase] = index + 1
        call = None
        if phase == "spawn" and index == 0:
            call = ("daily_driver_set_session_title", {"title": "Child ownership proof"})
        elif phase == "spawn" and index == 1:
            call = ("task", {"i":"Running isolated child proof", "context":"Isolated ownership proof; no external services.",
                "tasks":[{"agent":"child-proof", "name":"ChildProof", "task":"CHILD_PROOF_TARGET: return CHILD_PARKED with no tools.",
                          "solutionSpace":"Return the specified constant in the isolated harness."}]})
        elif phase == "spawn" and index == 2:
            call = ("wait", {"i":"Waiting for isolated child"})
        elif phase == "relay" and index == 0:
            call = ("write", {"i":"Reattaching isolated child", "path":"agent://ChildProof", "content":"CHILD_RELAY: return CHILD_RESUMED with no tools."})
        elif phase == "relay" and index == 1:
            call = ("wait", {"i":"Waiting for reattached child"})
        if call:
            name, parameters = call
            message = {"role":"assistant", "tool_calls":[{"index":0,"id":f"{phase}-{index}","type":"function",
                "function":{"name":name,"arguments":json.dumps(parameters)}}]}
            finish = "tool_calls"
        else:
            message = {"role":"assistant", "content":"CHILD_RESUMED" if "CHILD_RELAY" in prompt else "PROOF_SETTLED"}
            finish = "stop"
        chunks = [
            {"id":"child-proof","object":"chat.completion.chunk","model":"proof","choices":[{"index":0,"delta":message}]},
            {"id":"child-proof","object":"chat.completion.chunk","model":"proof","choices":[{"index":0,"delta":{},"finish_reason":finish}],
             "usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}},
        ]
        payload = ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def state(rpc, identifier, command):
    """Read a supported RPC state command without publishing full snapshots."""
    rpc.send({"id":identifier,"type":command})
    response = rpc.until(lambda frame: frame.get("type") == "response" and frame.get("id") == identifier)
    assert response.get("success"), {"command":command,"success":False}
    return response.get("data", {})


def agents(snapshot):
    """Normalize only the documented registry snapshot's synthetic fixture data."""
    if isinstance(snapshot, list):
        return snapshot
    for key in ("agents", "subagents"):
        if isinstance(snapshot.get(key), list):
            return snapshot[key]
    raise AssertionError({"registry_response_keys": sorted(snapshot)})


def main():
    """Compare actual agent bindings, not just a saved session's continued text."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory(prefix="omp-child-ownership-") as temporary:
            base = Path(temporary)
            home = base / "home"
            agent = home / ".omp/agent"
            (agent / "agents").mkdir(parents=True)
            (base / "sandbox").mkdir()
            (agent / "config.yml").write_text("model: cold-proof/proof\n")
            (agent / "models.yml").write_text("providers:\n  cold-proof:\n"
                f"    baseUrl: http://127.0.0.1:{server.server_address[1]}/v1\n"
                "    api: openai-completions\n    apiKey: isolated-proof\n    models:\n"
                "      - id: proof\n        name: Child proof\n        api: openai-completions\n"
                "        contextWindow: 131072\n        maxTokens: 1024\n"
                "        cost: {input: 0, output: 0, cacheRead: 0, cacheWrite: 0}\n")
            (agent / "agents/child-proof.md").write_text("---\nname: child-proof\ndescription: Isolated child ownership proof\nmodel: cold-proof/proof\n---\nReturn only the requested constant. Never use a network or tool.\n")
            metadata_path = base / "agent-metadata.jsonl"
            observer = base / "metadata.mjs"
            observer.write_text('''import { appendFileSync } from "node:fs";
export default function(pi) {
 pi.on("before_agent_start", (_event,ctx) => {
  appendFileSync(''' + json.dumps(str(metadata_path)) + ''',JSON.stringify({
   session:ctx.sessionManager.getSessionId(),file:ctx.sessionManager.getSessionFile(),
   agent:{kind:ctx.agent.kind,id:ctx.agent.id,name:ctx.agent.name,parentId:ctx.agent.parentId}
  })+"\\n",{mode:0o600});
 });
}
''')
            env = {key:os.environ[key] for key in ("PATH","LANG","TERM","TMPDIR") if key in os.environ}
            env["HOME"] = str(home)
            for key in ("XDG_CONFIG_HOME","XDG_DATA_HOME","XDG_STATE_HOME","XDG_CACHE_HOME"):
                env[key] = str(home / key.lower())
            extensions = [ROOT / "extensions/daily-driver.js", observer]
            rpc = FIXTURE.Rpc(base, env, extensions=extensions, tools="read,write,task,wait")
            try:
                rpc.send({"id":"spawn","type":"prompt","message":"SPAWN_CHILD_PROOF: run the single isolated child."})
                rpc.terminal()
                root_state = state(rpc, "root-state", "get_state")
                before = state(rpc, "children", "get_subagents")
            finally:
                rpc.close()
            metadata = [json.loads(line) for line in metadata_path.read_text().splitlines()]
            child = next((entry for entry in metadata if entry["agent"]["kind"] == "sub"), None)
            assert child, {"metadata_kinds":[item["agent"]["kind"] for item in metadata],"counts":COUNTS}
            child_header = None
            with open(child["file"]) as source:
                for _ in range(3):
                    entry = json.loads(source.readline())
                    if entry.get("type") == "session":
                        child_header = {key:entry.get(key) for key in ("id","parentSession","cwd")}
                        break
            direct = FIXTURE.Rpc(base, env, extensions=extensions, extra_args=["--resume",child["file"]],tools="read,write")
            try:
                direct.send({"id":"direct","type":"prompt","message":"CHILD_COLD_DIRECT: return the bounded constant."})
                direct.terminal()
                direct_state = state(direct, "direct-state", "get_state")
            finally:
                direct.close()
            after_direct = [json.loads(line) for line in metadata_path.read_text().splitlines()][-1]
            attempts = []
            for flag in ("--resume", "--restore"):
                try:
                    restored = FIXTURE.Rpc(base, env, extensions=extensions, extra_args=[flag,root_state["sessionFile"]], tools="read,write,task,wait")
                except AssertionError as error:
                    if flag == "--restore" and "--restore requires an interactive terminal" in str(error):
                        attempts.append({"flag":flag,"unsupported":"requires interactive terminal; RPC rejected"})
                        continue
                    raise
                try:
                    children = state(restored, "restored-children", "get_subagents")
                    snapshots = agents(children)
                    attempts.append({"flag":flag,"children":[{key:item.get(key) for key in ("id","name","status","sessionFile")} for item in snapshots]})
                    if snapshots:
                        COUNTS["relay"] = 0
                        restored.send({"id":"relay","type":"prompt","message":"ROOT_RELAY_CHILD: reattach only the existing ChildProof child."})
                        restored.terminal()
                        attempts[-1]["relay_requested"] = True
                finally:
                    restored.close()
            print(json.dumps({"original_child_agent":child["agent"],"direct_resumed_agent":after_direct["agent"],
                "same_session_id":direct_state["sessionId"] == child["session"],
                "child_header_has_parent":bool(child_header and child_header.get("parentSession")),
                "original_children":len(agents(before)),"root_recovery":attempts,
                "external_requests":0},indent=2))
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
