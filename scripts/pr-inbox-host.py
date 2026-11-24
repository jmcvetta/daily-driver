#!/usr/bin/env python3
"""Deliver durable owner inbox work through exclusively acquired Omp RPC.

Existing held owners receive through their opt-in extension. This host never
opens a held/unknown session, copies credentials, or mutates GitHub. A service
manager must restart this command; --once is useful for isolated proof.
"""
from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("pr_inbox", ROOT / "scripts/pr-inbox.py")
INBOX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INBOX)


def activate(inbox, owner, omp, timeout=90):
    """Resume only a provably free owner and verify its recorded route and ID."""
    lease = subprocess.run([omp, "session", "lease", "--json", "--", owner["session"]],
        capture_output=True, text=True, check=True, timeout=15)
    state = json.loads(lease.stdout)
    if state.get("unknown") or owner["session"] in state.get("held", []):
        return "owner-held-or-unknown"
    if state != {"held": [], "unknown": []}:
        raise RuntimeError("malformed session lease response")
    if not Path(owner["file"]).is_file() or not Path(owner["cwd"]).is_dir():
        raise RuntimeError("recorded owner transcript or worktree is unavailable")
    env = dict(os.environ, DAILY_DRIVER_PR_INBOX=str(inbox.path),
               DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER=owner["session"])
    command = [omp, "--mode", "rpc", "--resume", owner["file"], "--cwd", owner["cwd"],
               "--extension", str(ROOT / "extensions/pr-supervision-inbox.mjs"),
               "--model", f'{owner["provider"]}/{owner["model"]}', "--thinking", owner["effort"]]
    with tempfile.TemporaryFile(mode="w+t") as errors:
        process = subprocess.Popen(command, cwd=owner["cwd"], env=env, stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=errors, text=True, bufsize=1)
        frames = queue.Queue()

        def collect():
            for line in process.stdout:
                try:
                    frames.put(json.loads(line))
                except json.JSONDecodeError:
                    frames.put({"type": "invalid_frame"})
            frames.put(None)

        threading.Thread(target=collect, daemon=True).start()
        deadline = time.monotonic() + timeout
        checked = False
        terminal = False
        try:
            while time.monotonic() < deadline:
                try:
                    frame = frames.get(timeout=max(0.01, deadline - time.monotonic()))
                except queue.Empty:
                    break
                if frame is None:
                    raise RuntimeError("owner RPC ended before receipt")
                if frame.get("type") in ("extension_error", "invalid_frame", "rpc_frame_error"):
                    raise RuntimeError("owner RPC extension or framing failed")
                if frame.get("type") == "ready":
                    process.stdin.write('{"id":"owner-identity","type":"get_state"}\n')
                    process.stdin.flush()
                if frame.get("type") == "response" and frame.get("id") == "owner-identity":
                    actual = frame.get("data", {})
                    model = actual.get("model", {})
                    if (not frame.get("success") or actual.get("sessionId") != owner["session"]
                            or model.get("provider") != owner["provider"] or model.get("id") != owner["model"]):
                        raise RuntimeError("owner identity or route changed; refusing delivery")
                    checked = True
                if frame.get("type") == "agent_end" and frame.get("isTerminal") is not False:
                    terminal = True
                if checked and terminal:
                    remaining = inbox.db.execute("""SELECT count(*) FROM deliveries WHERE session=?
                        AND status IN ('pending','admitted') AND held IS NULL""", (owner["session"],)).fetchone()[0]
                    if remaining == 0:
                        return "received"
            raise TimeoutError("owner receipt deadline exceeded")
        finally:
            # Closing the owned RPC input is the documented graceful lifecycle.
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


def pass_once(inbox, omp):
    """Recover due durable owners without stealing live or unknown sessions."""
    sessions = [row[0] for row in inbox.db.execute("""SELECT DISTINCT session FROM deliveries
        WHERE status IN ('pending','admitted') AND held IS NULL AND attempts<5 AND next_attempt<=?""", (time.time(),))]
    results = []
    for session in sessions:
        owner = inbox.db.execute("SELECT * FROM owners WHERE session=?", (session,)).fetchone()
        if owner is None:
            outcome = "owner-context-unavailable"
        elif owner["heartbeat"] > time.time() - 10:
            outcome = "live-extension-owner"
        else:
            try:
                outcome = activate(inbox, dict(owner), omp)
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
                outcome = f"degraded:{type(error).__name__}"
        if outcome != "received":
            inbox.db.execute("""UPDATE deliveries SET last_error=? WHERE session=?
                AND status IN ('pending','admitted')""", (outcome, session))
        results.append({"session": session, "outcome": outcome})
    return results


def main():
    """Run one exclusive durable transport host, optionally for one bounded pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    omp = shutil.which("omp")
    if not omp:
        raise RuntimeError("omp is required")
    inbox = INBOX.Inbox(args.database)
    try:
        descriptor = os.open(str(inbox.path) + ".host-lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            while True:
                print(json.dumps(pass_once(inbox, omp)), flush=True)
                if args.once:
                    return
                threading.Event().wait(1)
    finally:
        inbox.close()


if __name__ == "__main__":
    main()
