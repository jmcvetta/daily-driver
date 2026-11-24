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


class ActivationError(RuntimeError):
    """Report a fixed nonsecret activation failure category."""

    def __init__(self, code):
        self.code = code
        super().__init__(code)


def activate(inbox, owner, omp, timeout=90):
    """Resume only a provably free owner and verify its recorded route and ID."""
    targets = [row[0] for row in inbox.db.execute("""SELECT identity FROM deliveries WHERE session=?
            AND status IN ('pending','admitted') AND held IS NULL""", (owner["session"],))]
    if not targets:
        return "stopped-or-idle"
    lease = subprocess.run([omp, "session", "lease", "--json", "--", owner["session"]],
        capture_output=True, text=True, check=True, timeout=15)
    state = json.loads(lease.stdout)
    if state.get("unknown") or owner["session"] in state.get("held", []):
        return "owner-held-or-unknown"
    if state != {"held": [], "unknown": []}:
        raise ActivationError("lease-response-invalid")
    if not Path(owner["file"]).is_file() or not Path(owner["cwd"]).is_dir():
        raise ActivationError("owner-context-unavailable")
    with open(owner["file"]) as saved:
        header = next((entry for _ in range(3)
                       if (line := saved.readline())
                       and (entry := json.loads(line)).get("type") == "session"), None)
    if not header or header.get("id") != owner["session"]:
        raise ActivationError("owner-session-header-invalid")
    activation_owner = owner
    binding = json.loads(owner.get("agent", "{}"))
    if header.get("parentSession"):
        if binding.get("kind") != "sub" or not binding.get("id"):
            raise ActivationError("child-or-fork-binding-unavailable")
        parent_file = header["parentSession"]
        visited = {owner["session"]}
        while True:
            parent = inbox.db.execute("SELECT * FROM owners WHERE file=?", (parent_file,)).fetchone()
            if parent is None or parent["session"] in visited:
                raise ActivationError("parent-owner-context-unavailable")
            activation_owner = dict(parent)
            visited.add(parent["session"])
            if json.loads(parent["agent"]).get("kind") == "main":
                break
            with open(parent["file"]) as saved:
                parent_header = next((entry for _ in range(3)
                    if (line := saved.readline()) and (entry := json.loads(line)).get("type") == "session"), None)
            if not parent_header or not parent_header.get("parentSession"):
                raise ActivationError("parent-chain-invalid")
            parent_file = parent_header["parentSession"]
        parent_lease = subprocess.run([omp, "session", "lease", "--json", "--", activation_owner["session"]],
            capture_output=True, text=True, check=True, timeout=15)
        if json.loads(parent_lease.stdout) != {"held": [], "unknown": []}:
            return "parent-held-or-unknown"
        if activation_owner.get("authentication", "unknown") == "unknown" or activation_owner["authentication"].startswith("env:"):
            raise ActivationError("parent-authentication-route-unavailable")
    if owner.get("authentication", "unknown") == "unknown" or owner.get("authentication", "").startswith("env:"):
        raise ActivationError("authentication-route-unavailable; environment credentials are not forwarded")
    allowed = ("HOME", "PATH", "LANG", "TERM", "TMPDIR", "OMP_PROFILE",
               "PI_CODING_AGENT_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
               "XDG_STATE_HOME", "XDG_CACHE_HOME", "XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS")
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env.update(DAILY_DRIVER_PR_INBOX=str(inbox.path),
               DAILY_DRIVER_PR_INBOX_EXPECTED_OWNER=owner["session"],
               DAILY_DRIVER_PR_INBOX_EXPECTED_AUTH=owner["authentication"])
    env["DAILY_DRIVER_PR_INBOX_EXPECTED_ROUTE"] = json.dumps({
        "provider":owner["provider"],"model":owner["model"],"effort":owner["effort"],"cwd":owner["cwd"]}, separators=(",", ":"))
    if binding:
        env["DAILY_DRIVER_PR_INBOX_EXPECTED_AGENT"] = json.dumps(binding, separators=(",", ":"))
    if activation_owner is not owner:
        env["DAILY_DRIVER_PR_INBOX_PARENT"] = activation_owner["session"]
        env["DAILY_DRIVER_PR_INBOX_PARENT_ROUTE"] = json.dumps({
            "provider":activation_owner["provider"],"model":activation_owner["model"],
            "effort":activation_owner["effort"],"authentication":activation_owner["authentication"],
            "agent":json.loads(activation_owner["agent"])}, separators=(",", ":"))
    command = [omp, "--mode", "rpc", "--resume", activation_owner["file"], "--cwd", activation_owner["cwd"],
               "--extension", str(ROOT / "extensions/pr-supervision-inbox.mjs"),
               "--model", f'{activation_owner["provider"]}/{activation_owner["model"]}', "--thinking", activation_owner["effort"]]
    with tempfile.TemporaryFile(mode="w+t") as errors:
        process = subprocess.Popen(command, cwd=activation_owner["cwd"], env=env, stdin=subprocess.PIPE,
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
        running = False
        try:
            while running or time.monotonic() < deadline:
                current = [inbox.get(key) for key in targets]
                if all(row["status"] == "stopped" or row["held"] for row in current):
                    process.stdin.write('{"id":"fenced-owner","type":"abort"}\n')
                    process.stdin.flush()
                    return "stopped-or-idle"
                try:
                    frame = frames.get(timeout=1 if running else min(1,max(0.01, deadline - time.monotonic())))
                except queue.Empty:
                    if running or time.monotonic() < deadline:
                        continue
                    break
                if frame is None:
                    raise ActivationError("owner-rpc-ended-before-receipt")
                if frame.get("type") in ("extension_error", "invalid_frame", "rpc_frame_error"):
                    raise ActivationError("owner-rpc-extension-or-framing")
                if frame.get("type") == "ready":
                    process.stdin.write('{"id":"owner-identity","type":"get_state"}\n')
                    process.stdin.flush()
                if frame.get("type") == "response" and frame.get("id") == "owner-identity":
                    actual = frame.get("data", {})
                    model = actual.get("model", {})
                    if (not frame.get("success") or actual.get("sessionId") != activation_owner["session"]
                            or model.get("provider") != activation_owner["provider"] or model.get("id") != activation_owner["model"]):
                        raise ActivationError("owner-identity-or-route-changed")
                    checked = True
                    if activation_owner is not owner:
                        # The supported parent native write resolver revives the
                        # persisted child; direct child --resume changes its role.
                        process.stdin.write(json.dumps({"id":"child-dispatch","type":"prompt",
                            "message":f"Recovery carrier only: use native write to agent://{binding['id']} with content "
                                      "'Resume the fenced PR inbox work', then wait for that child. "
                                      "Do not create a child or perform any other work."}) + "\n")
                        process.stdin.flush()
                if frame.get("type") == "agent_start":
                    running = True
                    terminal = False
                if frame.get("type") == "agent_end" and frame.get("isTerminal") is not False:
                    terminal = True
                    running = False
                if checked and terminal:
                    remaining = inbox.db.execute("""SELECT count(*) FROM deliveries WHERE session=?
                        AND status IN ('pending','admitted') AND held IS NULL""", (owner["session"],)).fetchone()[0]
                    if remaining == 0:
                        received = inbox.db.execute("SELECT 1 FROM deliveries WHERE session=? AND status='received' LIMIT 1",
                                                    (owner["session"],)).fetchone()
                        return "received" if received else "stopped-or-idle"
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


def deliver(inbox, owner, omp, clock=None):
    """Bound pre-admission failures as well as delivered-but-unacknowledged work."""
    clock = clock or time.time
    before = [dict(row) for row in inbox.db.execute("""SELECT identity,generation,fence,attempts FROM deliveries
        WHERE session=? AND status IN ('pending','admitted') AND held IS NULL AND attempts<5""", (owner["session"],))]
    try:
        outcome = activate(inbox, owner, omp)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
        outcome = f"degraded:{getattr(error, 'code', type(error).__name__)}"
    if outcome != "received":
        busy = outcome in ("owner-held-or-unknown","parent-held-or-unknown","stopped-or-idle")
        with inbox.transaction():
            for row in before:
                inbox.db.execute("""UPDATE deliveries SET last_error=?,next_attempt=MAX(next_attempt,?),
                    attempts=MAX(attempts,?) WHERE identity=? AND generation=? AND fence=?
                    AND status IN ('pending','admitted')""",
                    (outcome,clock()+120,row["attempts"]+int(not busy),row["identity"],row["generation"],row["fence"]))
    return outcome


def pass_once(inbox, omp):
    """Recover due durable owners without stealing live or unknown sessions."""
    sessions = [row[0] for row in inbox.db.execute("""SELECT DISTINCT session FROM deliveries
        WHERE status IN ('pending','admitted') AND held IS NULL AND attempts<5 AND next_attempt<=?""", (time.time(),))]
    results = []
    for session in sessions:
        owner = inbox.db.execute("SELECT * FROM owners WHERE session=?", (session,)).fetchone()
        if owner is None:
            outcome = "owner-context-unavailable"
            inbox.db.execute("""UPDATE deliveries SET attempts=attempts+1 WHERE session=?
                AND status IN ('pending','admitted') AND held IS NULL AND attempts<5""", (session,))
        elif owner["heartbeat"] > time.time() - 10:
            outcome = "live-extension-owner"
        else:
            outcome = deliver(inbox, dict(owner), omp)
        if outcome not in ("received", "live-extension-owner"):
            inbox.db.execute("""UPDATE deliveries SET last_error=?,next_attempt=MAX(next_attempt,?) WHERE session=?
                AND status IN ('pending','admitted')""", (outcome, time.time() + 120, session))
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
