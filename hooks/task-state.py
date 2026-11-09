#!/usr/bin/env python3
"""Bind native hook events and tool calls to one private, atomically updated task ledger."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
RECEIPT = "daily-driver.task-receipt"
RECEIPT_LIMIT = 20


def _path(base: Path, harness: str, session: str, agent: str) -> Path:
    identity = json.dumps([harness, session, agent], separators=(",", ":"))
    return base / (hashlib.sha256(identity.encode()).hexdigest() + ".json")


def _load(path: Path) -> dict:
    if not path.exists():
        return {"schemaVersion": 1, "entries": []}
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=("claude", "codex"), required=True)
    parser.add_argument("--session")
    parser.add_argument("--agent", default="")
    parser.add_argument("--parent", default="", help="Direct parent agent of a nested subagent; the root session when empty")
    parser.add_argument("--tool", action="store_true",
                        help="Task-state command route: accepts only {action, record}, never a hook event")
    args = parser.parse_args()
    data = json.load(sys.stdin)
    if not isinstance(data, dict):
        raise ValueError("Task-state input must be a JSON object")
    tool = args.tool
    # The command route the model is given must not be able to inject a user prompt, Stop or Interrupt event.
    if tool and ("action" not in data or {"hook_event_name", "name"} & data.keys()):
        raise ValueError("The task-state command accepts only {action, record}")
    if not tool and "action" in data:
        raise ValueError("Hook events cannot carry task-state actions; use the --tool route")
    session = args.session if tool else data.get("session_id", args.session)
    agent = args.agent if tool else data.get("agent_id", args.agent)
    if not isinstance(session, str) or not session or not isinstance(agent, str):
        raise ValueError("Native session identity is required; task prose cannot supply it")
    config = os.environ.get("CODEX_HOME") if args.harness == "codex" else os.environ.get("CLAUDE_CONFIG_DIR")
    base = Path(config or Path.home() / (".codex" if args.harness == "codex" else ".claude")) / "daily-driver-task-contracts"
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(base, 0o700)
    path = _path(base, args.harness, session, agent)
    command = ["python3", str(Path(__file__).resolve()), "--harness", args.harness, "--tool", "--session", session]
    if agent:
        command += ["--agent", agent]
    if agent and args.parent:
        command += ["--parent", args.parent]
    with path.with_suffix(".lock").open("a", encoding="utf-8") as lock:
        os.chmod(lock.name, 0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger = _load(path)
        parent = _load(_path(base, args.harness, session, args.parent)) if agent else None
        # A nested child adopts its direct parent's contract but must still resolve the root's original sources.
        root = _load(_path(base, args.harness, session, "")) if agent and args.parent else None
        request = {"harness": args.harness, "sessionId": session, "agentId": agent or None,
                   "cwd": data.get("cwd", os.getcwd()), "ledger": ledger, "parentLedger": parent, "rootLedger": root,
                   "toolCommand": shlex.join(command)}
        response = None
        if tool:
            request.update(action=data["action"], record=data.get("record"))
            if isinstance(request["record"], str):
                try:
                    request["record"] = json.loads(request["record"])
                except json.JSONDecodeError as error:
                    response = {"ledger": json.loads(json.dumps(ledger)), "output": {
                        "content": [{"type": "text", "text": f"record must be a JSON object: {error}"}], "isError": True}}
        else:
            request["event"] = data
        if response is None:
            result = subprocess.run(["node", str(ROOT / "hooks/task-state.mjs")], input=json.dumps(request),
                                    text=True, capture_output=True, timeout=10, check=False)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or "Task controller did not return a result")
            response = json.loads(result.stdout)
        text = json.dumps(response["output"])
        if tool and args.harness == "codex":
            # The hook drops a shell result whose output is exactly this text, so the model's
            # own bookkeeping call is not task evidence; nothing parses the command.
            entries = response["ledger"]["entries"]
            receipts = [index for index, entry in enumerate(entries) if entry.get("customType") == RECEIPT]
            for index in reversed(receipts[:max(0, len(receipts) + 1 - RECEIPT_LIMIT)]):
                del entries[index]
            entries.append({"type": "custom", "customType": RECEIPT,
                            "data": {"digest": hashlib.sha256(text.encode()).hexdigest()}})
        if response["ledger"] != ledger:
            descriptor, temporary = tempfile.mkstemp(prefix=path.stem + ".", dir=base)
            try:
                with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                    json.dump(response["ledger"], target, separators=(",", ":"))
                    target.flush()
                    os.fsync(target.fileno())
                os.replace(temporary, path)
                directory = os.open(base, os.O_RDONLY | os.O_DIRECTORY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        # A controller answer exits 0 even when it reports isError, so a bookkeeping call never
        # registers as a failed tool result; only protocol and runtime faults exit nonzero.
        sys.stdout.write(text)


if __name__ == "__main__":
    try:
        _main()
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Daily Driver task-state error: {error}", file=sys.stderr)
        raise SystemExit(1) from error
