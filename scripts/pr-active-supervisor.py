#!/usr/bin/env python3
"""Reconcile opted-in PR actors and deliver only changed actionable work.

Activation transfers existing Omp service ownership; it does not install a
lifecycle host. Shadow records cannot update GitHub or enqueue owner work.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import uuid

ROOT = Path(__file__).resolve().parent.parent


def load(name, filename):
    """Load shipped Python components without adding a packaging dependency."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHADOW = load("pr_supervisor", "pr-supervisor.py")
INBOX = load("pr_inbox", "pr-inbox.py")
HOST = load("pr_inbox_host", "pr-inbox-host.py")


class ActiveSupervisor:
    """Own one fenced authority record per PR and reuse its durable observation."""

    def __init__(self, path, clock=time.time):
        self.ledger = SHADOW.Ledger(path)
        self.db = self.ledger.db
        self.inbox = INBOX.Inbox(path, connection=self.db)
        self.clock = clock
        with self.ledger.transaction():
            self.db.execute("""CREATE TABLE IF NOT EXISTS authorities (
                identity TEXT PRIMARY KEY, state TEXT NOT NULL
                CHECK(state IN ('shadow','transferring','active','rollback')),
                epoch INTEGER NOT NULL DEFAULT 0, legacy TEXT NOT NULL DEFAULT '{}',
                acknowledged INTEGER NOT NULL DEFAULT 0, ack_evidence TEXT, update_head TEXT,
                update_started REAL, error TEXT)""")

    def close(self):
        """Release the local database without releasing or stopping durable actors."""
        self.ledger.close()

    def host_running(self):
        """Probe the active controller's held file lease without reading its environment."""
        descriptor = os.open(str(self.ledger.path) + ".actor-lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "r+") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return False
            except BlockingIOError:
                return True

    def register(self, host, repository, number, login, context):
        """Register created/adopted PRs in shadow without stealing another owner."""
        if not all(context.get(field) for field in ("session", "worktree", "branch", "task")):
            raise ValueError("persisted session, worktree, branch and task context are required")
        record = self.ledger.register(host, repository, number, login, context, self.clock())
        with self.ledger.transaction():
            self.db.execute("INSERT OR IGNORE INTO authorities(identity,state) VALUES (?,'shadow')", (record["identity"],))
        return self.status(record["identity"])

    def status(self, key):
        """Read current authority, observation and pending delivery without secrets."""
        record = self.ledger.get(key)
        row = self.db.execute("SELECT * FROM authorities WHERE identity=?", (key,)).fetchone()
        record["authority"] = dict(row) if row else {"state": "shadow"}
        delivery = self.db.execute("SELECT * FROM deliveries WHERE identity=?", (key,)).fetchone()
        record["delivery"] = dict(delivery) if delivery else None
        record["host_running"] = self.host_running()
        return record

    def source(self, key):
        """Construct the authoritative GitHub reader for the stored identity."""
        record = self.ledger.get(key)
        return GitHub(record["host"], record["repository"], record["number"], record["owner"],
                      json.loads(record["context"])["session"])

    def _persist(self, record):
        key = record["identity"]
        actor = self.db.execute("SELECT * FROM authorities WHERE identity=?", (key,)).fetchone()
        delivery = self.db.execute("SELECT * FROM deliveries WHERE identity=?", (key,)).fetchone()
        if record["stopped"]:
            if delivery:
                self.inbox.stop(key)
            self.db.execute("UPDATE authorities SET epoch=epoch+1,update_head=NULL WHERE identity=?", (key,))
            return
        if record["held"]:
            if delivery:
                self.inbox.hold(key, record["held"])
            return
        if not actor or actor["state"] != "active":
            return
        proposal = json.loads(record["proposal"]) if record["proposal"] else None
        if not proposal or not proposal["reasons"]:
            return
        context = json.loads(record["context"])
        payload = {"kind": "pr-supervisor-work", "identity": key,
                   "context": context, "proposal": proposal,
                   "observed": json.loads(record["observed"]) if record["observed"] else None,
                   "degraded": record["degraded"], "outage": {"start":record["gap_start"],"end":record["gap_end"]}}
        self.inbox.enqueue(key, context["session"], record["generation"], payload, self.clock())

    def control(self, key, operation, reason):
        """Atomically fence PR observation and pending delivery before returning."""
        result = self.ledger.control(key, operation, reason, self.clock(), persist=self._persist)
        if operation == "release":
            with self.ledger.transaction():
                delivery = self.db.execute("SELECT * FROM deliveries WHERE identity=?", (key,)).fetchone()
                if delivery and delivery["held"]:
                    self.inbox.release(key)
        if operation == "stop":
            authority = self.db.execute("SELECT legacy FROM authorities WHERE identity=?", (key,)).fetchone()
            context = json.loads(result["context"])
            for service in json.loads(authority["legacy"]).get("services", []) if authority else []:
                service_control("stop", service, context)
        return result

    def hint(self, key):
        """Coalesce a verified event hint into an earlier authoritative read only."""
        with self.ledger.transaction():
            record = self.ledger.get(key)
            if not record["stopped"] and not record["held"]:
                self.db.execute("UPDATE records SET next_due=MIN(next_due,?) WHERE identity=?", (self.clock(), key))

    def reconcile(self, key, source=None):
        """Observe, recheck and conditionally update one current-head PR actor."""
        source = source or self.source(key)
        writer = str(uuid.uuid4())
        epoch = self.ledger.acquire(key, writer, self.clock())
        if epoch is None:
            return self.status(key)
        try:
            snapshot = source.observe()
            with self.ledger.transaction():
                record = self.ledger.get(key)
                actor = self.db.execute("SELECT * FROM authorities WHERE identity=?", (key,)).fetchone()
                if (record["stopped"] or record["held"] or record["epoch"] != epoch
                        or record["lease_owner"] != writer or record["lease_until"] <= self.clock()):
                    raise SHADOW.Fenced("actor was stopped, held or superseded")
                if actor and actor["state"] == "active" and snapshot["state"] == "OPEN":
                    if actor["update_head"]:
                        if actor["update_head"] != snapshot["head"] or snapshot["currency"] == "current":
                            self.db.execute("UPDATE authorities SET update_head=NULL,update_started=NULL,error=NULL WHERE identity=?", (key,))
                        elif self.clock() - actor["update_started"] > 120:
                            raise SHADOW.ObservationError("server update has not settled; diagnose before retry")
                    elif snapshot["currency"] == "update_candidate" and snapshot["ci"] not in ("in_flight", "unregistered"):
                        # Keep stop/ownership controls serialized through this bounded
                        # remote call. Stop commits only after an in-flight mutation
                        # exits, and always before its caller's stop-time push.
                        latest = source.observe()
                        if record["lease_until"] <= self.clock():
                            raise SHADOW.Fenced("lease expired during pre-update observation")
                        if (latest["state"] == "OPEN" and latest["head"] == snapshot["head"]
                                and latest["base"] == snapshot["base"] and latest["currency"] == "update_candidate"
                                and latest["ci"] not in ("in_flight", "unregistered")):
                            self.db.execute("UPDATE authorities SET update_head=?,update_started=? WHERE identity=?",
                                            (latest["head"], self.clock(), key))
                            source.update(latest["head"])
                            snapshot = source.observe()
                        else:
                            snapshot = latest
            self.ledger.finish(key, writer, epoch, self.clock(), snapshot=snapshot, persist=self._persist)
        except SHADOW.ObservationError as error:
            self.ledger.finish(key, writer, epoch, self.clock(), error=str(error), persist=self._persist)
        return self.status(key)

    def acknowledge(self, key, generation, fence, admission, source=None):
        """Acknowledge work only after this owner action makes a fresh GitHub read."""
        record = self.ledger.get(key)
        delivery = self.inbox.get(key)
        if (record["stopped"] or record["held"] or delivery["held"] or delivery["status"] != "admitted"
                or delivery["generation"] != generation or delivery["fence"] != fence
                or delivery["admission"] != admission):
            return {"acknowledged": False, "reason": "stale, stopped or held delivery"}
        fresh = (source or self.source(key)).observe()
        with self.ledger.transaction():
            record = self.ledger.get(key)
            actor = self.db.execute("SELECT * FROM authorities WHERE identity=?", (key,)).fetchone()
            delivery = self.inbox.get(key)
            payload = json.loads(delivery["payload"])
            expected_head = (payload.get("observed") or {}).get("head")
            if (record["stopped"] or record["held"] or delivery["held"] or actor["state"] != "active"
                    or actor["update_head"] or fresh["head"] != expected_head or fresh["state"] != "OPEN"
                    or delivery["status"] != "admitted" or delivery["generation"] != generation
                    or delivery["fence"] != fence or delivery["admission"] != admission):
                self.db.execute("UPDATE records SET next_due=MIN(next_due,?) WHERE identity=?", (self.clock(), key))
                return {"acknowledged": False, "reason": "stale, stopped, held or changed authoritative evidence"}
            self.db.execute("UPDATE deliveries SET status='received',receipt=? WHERE identity=?", (self.clock(), key))
            self.db.execute("UPDATE authorities SET acknowledged=MAX(acknowledged,?),ack_evidence=? WHERE identity=?",
                            (generation, json.dumps(fresh), key))
            return {"acknowledged": True, "generation": generation, "head": fresh["head"], "observed": fresh}

    def transfer(self, key, services, cancelled_timers, process_control=None):
        """Fence handoff, stop verified legacy actors, then activate one authority."""
        if not self.host_running():
            raise RuntimeError("active lifecycle controller is unavailable; keep the prior route authoritative")
        record = self.ledger.get(key)
        context = json.loads(record["context"])
        with self.ledger.transaction():
            actor = self.db.execute("SELECT * FROM authorities WHERE identity=?", (key,)).fetchone()
            if actor["state"] == "active":
                return self.status(key)
            if record["stopped"] or record["held"]:
                raise ValueError("stopped or held PR cannot transfer")
            self.db.execute("UPDATE authorities SET state='transferring',epoch=epoch+1,legacy=?,error=NULL WHERE identity=?",
                (json.dumps({"services": services, "timers": cancelled_timers}), key))
            self.db.execute("UPDATE records SET epoch=epoch+1,lease_owner=NULL,lease_until=0 WHERE identity=?", (key,))
            transfer_epoch = self.db.execute("SELECT epoch FROM authorities WHERE identity=?", (key,)).fetchone()[0]
        control = process_control or service_control
        try:
            for service in services:
                control("stop", service, context)
            # Fresh state is required before activation, not a stale transfer receipt.
            snapshot = self.source(key).observe()
            with self.ledger.transaction():
                record = self.ledger.get(key)
                if record["stopped"] or record["held"]:
                    raise ValueError("PR stopped or held during transfer")
                if self.db.execute("SELECT epoch FROM authorities WHERE identity=?", (key,)).fetchone()[0] != transfer_epoch:
                    raise SHADOW.Fenced("transfer was superseded")
                self.db.execute("UPDATE authorities SET state='active',epoch=epoch+1 WHERE identity=?", (key,))
                self.db.execute("UPDATE records SET next_due=? WHERE identity=?", (self.clock(), key))
                if snapshot["state"] != "OPEN":
                    self.db.execute("UPDATE records SET stopped=?,epoch=epoch+1 WHERE identity=?", (snapshot["state"].lower(), key))
                    self._persist(self.ledger.get(key))
            return self.status(key)
        except BaseException:
            with self.ledger.transaction():
                self.db.execute("UPDATE authorities SET error='transfer incomplete; legacy actors may be stopped' WHERE identity=?", (key,))
            raise

    def rollback(self, key, process_control=None):
        """Fence the new actor before restoring saved old actors from fresh state."""
        with self.ledger.transaction():
            actor = self.db.execute("SELECT * FROM authorities WHERE identity=?", (key,)).fetchone()
            self.db.execute("UPDATE authorities SET state='rollback',epoch=epoch+1 WHERE identity=?", (key,))
            self.db.execute("UPDATE records SET epoch=epoch+1,lease_owner=NULL,lease_until=0 WHERE identity=?", (key,))
            delivery = self.db.execute("SELECT * FROM deliveries WHERE identity=?", (key,)).fetchone()
            if delivery:
                self.inbox.stop(key)
        record = self.ledger.get(key)
        if record["stopped"] or record["held"]:
            return {"restored": False, "reason": "stop/hold preserved", "timers": []}
        snapshot = self.source(key).observe()
        legacy = json.loads(actor["legacy"])
        if snapshot["state"] != "OPEN" or snapshot["currency"] == "conflict":
            return {"restored": False, "reason": "terminal PR or conflict; old actor remains stopped", "timers": []}
        context = json.loads(record["context"])
        with self.ledger.transaction():
            current = self.ledger.get(key)
            if current["stopped"] or current["held"]:
                return {"restored":False,"reason":"stop/hold preserved","timers":[]}
            for service in legacy.get("services", []):
                (process_control or service_control)("restart", service, context)
            self.db.execute("UPDATE authorities SET state='shadow',error=NULL WHERE identity=?", (key,))
        return {"restored": True, "timers": legacy.get("timers", []),
                "limitation": "old Omp route cannot cold-resume an owner after shutdown"}

class DeliveryHost:
    """Keep owned RPC work off the reconciliation loop without duplicate launches."""

    def __init__(self, actor):
        self.actor = actor
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="pr-owner")
        self.running = {}

    def _activate(self, owner):
        inbox = INBOX.Inbox(self.actor.ledger.path)
        try:
            return HOST.activate(inbox, owner, "omp")
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, TimeoutError) as error:
            return f"degraded:{getattr(error, 'code', type(error).__name__)}"
        finally:
            inbox.close()

    def poll(self):
        """Dispatch one cold activation per free owner and retain live owners."""
        events = []
        for session, future in list(self.running.items()):
            if future.done():
                outcome = future.result()
                del self.running[session]
                if outcome != "received":
                    self.actor.db.execute("""UPDATE deliveries SET last_error=?,next_attempt=MAX(next_attempt,?)
                        WHERE session=? AND status IN ('pending','admitted')""",
                        (outcome, self.actor.clock() + 120, session))
                events.append({"session":session,"outcome":outcome})
        due = list(self.actor.db.execute("""SELECT DISTINCT session FROM deliveries WHERE status IN ('pending','admitted')
            AND held IS NULL AND attempts<5 AND next_attempt<=?""", (self.actor.clock(),)))
        for (session,) in due:
            if session in self.running:
                continue
            owner = self.actor.db.execute("SELECT * FROM owners WHERE session=?", (session,)).fetchone()
            if owner is None:
                self.actor.db.execute("""UPDATE deliveries SET last_error='owner-context-unavailable',
                    next_attempt=? WHERE session=? AND status IN ('pending','admitted')""", (self.actor.clock() + 120, session))
                events.append({"session":session,"outcome":"owner-context-unavailable"})
            elif owner["heartbeat"] <= self.actor.clock() - 10:
                self.running[session] = self.executor.submit(self._activate, dict(owner))
        return events

    def close(self):
        """Retain admitted owner work until it settles, rather than timing it out."""
        self.executor.shutdown(wait=True)


def service_control(operation, service, context):
    """Stop/restart only an exact owned Omp actor; never retain its environment."""
    info = subprocess.run(["omp", "ps", "info", service, "--dir", context["worktree"], "--json"],
                          capture_output=True, text=True, check=True, timeout=15)
    metadata = json.loads(info.stdout)
    if (metadata.get("owner") != context["session"] or metadata.get("cwd") != context["worktree"]
            or metadata.get("key") != service):
        raise ValueError("legacy service is not owned by this PR context")
    # Raw info includes inherited environment. Never publish or persist it.
    del info, metadata
    subprocess.run(["omp", "ps", operation, service, "--dir", context["worktree"]],
                   check=True, capture_output=True, text=True, timeout=30)
    checked = subprocess.run(["omp", "ps", "info", service, "--dir", context["worktree"], "--json"],
                             check=True, capture_output=True, text=True, timeout=15)
    running = bool(json.loads(checked.stdout).get("pids"))
    if (operation == "stop" and running) or (operation == "restart" and not running):
        raise RuntimeError("legacy actor did not reach the requested stopped/running state")


class GitHub(SHADOW.GitHub):
    """Extend authoritative reads with only the server update-branch mutation."""

    def update(self, head):
        """Fence server-side update-branch against a changed head."""
        command = ["gh", "api", "--hostname", self.host, "--method", "PUT",
                   f"/repos/{self.repository}/pulls/{self.number}/update-branch",
                   "-f", f"expected_head_sha={head}"]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
        except (OSError, subprocess.SubprocessError) as error:
            raise SHADOW.ObservationError("server update-branch unavailable; reread before retry") from error


def main():
    """Expose scoped supervisor operations; run only under an authorized host."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--request", type=Path, required=True)
    for name in ("status", "hint", "reconcile", "rollback"):
        sub.add_parser(name).add_argument("identity")
    for name in ("stop", "hold", "release"):
        control = sub.add_parser(name)
        control.add_argument("identity")
        control.add_argument("--reason", required=True)
    transfer = sub.add_parser("transfer")
    transfer.add_argument("identity")
    transfer.add_argument("--request", type=Path, required=True)
    acknowledge = sub.add_parser("acknowledge")
    acknowledge.add_argument("identity")
    acknowledge.add_argument("--generation", type=int, required=True)
    acknowledge.add_argument("--fence", type=int, required=True)
    acknowledge.add_argument("--admission", required=True)
    sub.add_parser("run")
    sub.add_parser("initialize")
    args = parser.parse_args()
    actor = ActiveSupervisor(args.database)
    try:
        if args.command == "register":
            request = json.loads(sys.stdin.read() if str(args.request) == "-" else args.request.read_text())
            output = actor.register(request["host"], request["repository"], request["number"], request["login"], request["context"])
        elif args.command == "initialize":
            output = {"initialized": True, "schema": 1}
        elif args.command == "run":
            descriptor = os.open(str(actor.ledger.path) + ".actor-lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(descriptor, "w") as lock, closing(DeliveryHost(actor)) as deliveries:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                previous = None
                while True:
                    states = []
                    for key in actor.ledger.due(actor.clock()):
                        try:
                            record = actor.reconcile(key)
                            states.append({"identity": key, "generation": record["generation"], "degraded": record["degraded"]})
                        except SHADOW.Fenced:
                            states.append({"identity": key, "fenced": True})
                    states += deliveries.poll()
                    if states and states != previous:
                        print(json.dumps(states), flush=True)
                        previous = states
                    threading.Event().wait(1)
        elif args.command == "acknowledge":
            output = actor.acknowledge(args.identity, args.generation, args.fence, args.admission)
        elif args.command == "transfer":
            request = json.loads(sys.stdin.read() if str(args.request) == "-" else args.request.read_text())
            output = actor.transfer(args.identity, request["services"], request["cancelled_timers"])
        elif args.command == "rollback":
            output = actor.rollback(args.identity)
        elif args.command == "reconcile":
            output = actor.reconcile(args.identity)
        elif args.command == "status":
            output = actor.status(args.identity)
        elif args.command == "hint":
            actor.hint(args.identity)
            output = actor.status(args.identity)
        else:
            output = actor.control(args.identity, args.command, args.reason)
        if args.command != "run":
            print(json.dumps(output, sort_keys=True))
    finally:
        actor.close()


if __name__ == "__main__":
    main()
