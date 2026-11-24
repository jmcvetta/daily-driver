#!/usr/bin/env python3
"""Persist opt-in PR supervision observations without writes or agent delivery.

The existing maintenance route stays authoritative. This shadow consumer has
no update, wake, subscription, readiness, cutover, or resume operation.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import time
import uuid

INTERVAL = 120
LEASE_SECONDS = 110
SUCCESS = {"success", "neutral", "skipped"}


class ObservationError(Exception):
    """Represent unavailable or inconsistent authoritative GitHub evidence."""


class Fenced(Exception):
    """Reject an expired or superseded shadow observation writer."""


def identity(host, repository, number):
    """Validate and normalize one GitHub identity, including enterprise hosts."""
    if not re.fullmatch(r"[A-Za-z0-9.-]+", host) or host.startswith("-"):
        raise ValueError("host must be a hostname, not a URL")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("repository must be owner/name")
    if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
        raise ValueError("PR number must be positive")
    return f"{host.lower()}/{repository.lower()}/{number}"


def canonical(value):
    """Serialize normalized evidence consistently for durable comparisons."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class Ledger:
    """Serialize shadow registrations and fence observation results in SQLite."""

    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        if self.path.stat().st_mode & 0o077:
            raise ValueError("ledger must be owner-only (0600)")
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA synchronous=FULL")
        with self.transaction():
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported supervisor ledger schema")
            self.db.execute("""CREATE TABLE IF NOT EXISTS records (
                identity TEXT PRIMARY KEY, host TEXT NOT NULL, repository TEXT NOT NULL,
                number INTEGER NOT NULL, owner TEXT NOT NULL, context TEXT NOT NULL,
                mode TEXT NOT NULL CHECK(mode='shadow'), created REAL NOT NULL,
                stopped TEXT, held TEXT, epoch INTEGER NOT NULL DEFAULT 0,
                lease_owner TEXT, lease_until REAL NOT NULL DEFAULT 0,
                generation INTEGER NOT NULL DEFAULT 0, observed TEXT,
                proposal TEXT, last_observed REAL, next_due REAL NOT NULL,
                degraded TEXT, gap_start REAL, gap_end REAL
            )""")
            self.db.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self):
        """Hold an atomic writer transaction without spanning network calls."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        """Release this process's database connection without stopping records."""
        self.db.close()

    def get(self, key):
        """Return the durable record or reject an unregistered identity."""
        row = self.db.execute("SELECT * FROM records WHERE identity=?", (key,)).fetchone()
        if row is None:
            raise ValueError("PR is not registered")
        return dict(row)

    def register(self, host, repository, number, owner, context, now):
        """Adopt an existing identity without stealing context or clearing stops."""
        key = identity(host, repository, number)
        if not owner.strip() or not isinstance(context, dict) or not context:
            raise ValueError("owner and nonempty task context are required")
        with self.transaction():
            self.db.execute("""INSERT INTO records
                (identity,host,repository,number,owner,context,mode,created,next_due)
                VALUES (?,?,?,?,?,?,'shadow',?,?) ON CONFLICT(identity) DO NOTHING""",
                (key, host.lower(), repository.lower(), number, owner, canonical(context), now, now))
            return self.get(key)

    def control(self, key, operation, reason, now):
        """Fence shadow work before recording an explicit stop, hold, or release."""
        if operation not in ("stop", "hold", "release") or not reason.strip():
            raise ValueError("control requires stop, hold, or release and a reason")
        with self.transaction():
            record = self.get(key)
            if operation == "release" and record["stopped"]:
                raise ValueError("a stopped record cannot be released by a hold release")
            stopped = reason if operation == "stop" else record["stopped"]
            held = reason if operation == "hold" else None if operation == "release" else record["held"]
            self.db.execute("""UPDATE records SET stopped=?,held=?,epoch=epoch+1,
                lease_owner=NULL,lease_until=0,proposal=NULL,next_due=? WHERE identity=?""",
                (stopped, held, now, key))
            return self.get(key)

    def acquire(self, key, writer, now):
        """Acquire a fresh fencing epoch only when no live writer or hold exists."""
        with self.transaction():
            record = self.get(key)
            if record["stopped"] or record["held"] or record["lease_until"] > now:
                return None
            epoch = record["epoch"] + 1
            self.db.execute("""UPDATE records SET epoch=?,lease_owner=?,lease_until=?
                WHERE identity=?""", (epoch, writer, now + LEASE_SECONDS, key))
            return epoch

    def due(self, now):
        """Enumerate due shadow identities after a process restart as well as live."""
        return [row[0] for row in self.db.execute("""SELECT identity FROM records
            WHERE stopped IS NULL AND held IS NULL AND next_due<=? ORDER BY identity""", (now,))]

    def finish(self, key, writer, epoch, now, snapshot=None, error=None):
        """Commit one fenced observation, coalescing a proposal without delivery."""
        with self.transaction():
            record = self.get(key)
            if (record["epoch"] != epoch or record["lease_owner"] != writer
                    or record["lease_until"] <= now or record["stopped"] or record["held"]):
                raise Fenced("shadow observation lost its lease or was stopped/held")
            previous = json.loads(record["observed"]) if record["observed"] else None
            gap_start, gap_end = record["gap_start"], record["gap_end"]
            if record["last_observed"] is not None and now > record["next_due"]:
                if gap_start is None or gap_end is not None:
                    gap_start, gap_end = record["next_due"], None
            if error:
                proposal = {"reasons": ["observation_unavailable"], "next_action": "diagnose_access"}
                changed = error != record["degraded"]
                observed = record["observed"]
                degraded = error
                if gap_start is None or gap_end is not None:
                    gap_start = now
                gap_end = None
                stopped = None
            else:
                proposal = plan(previous, snapshot)
                observed = canonical(snapshot)
                degraded = None
                changed = observed != record["observed"] or record["degraded"] is not None
                if record["degraded"]:
                    proposal["reasons"] = sorted(set(proposal["reasons"] + ["observation_recovered"]))
                if gap_start is not None and gap_end is None:
                    gap_end = now
                stopped = snapshot["state"].lower() if snapshot["state"] in ("MERGED", "CLOSED") else None
            # Proposals are evidence, not a delivery queue. Terminal records retain
            # the terminal observation but fence and erase any outstanding proposal.
            generation = record["generation"] + int(changed)
            if stopped:
                proposal = None
            elif not changed:
                proposal = json.loads(record["proposal"]) if record["proposal"] else None
            self.db.execute("""UPDATE records SET observed=?,proposal=?,generation=?,
                degraded=?,gap_start=?,gap_end=?,last_observed=?,next_due=?,
                stopped=?,epoch=epoch+?,lease_owner=NULL,lease_until=0 WHERE identity=?""",
                (observed, canonical(proposal) if proposal else None, generation, degraded,
                 gap_start, gap_end, now, now + INTERVAL, stopped, int(stopped is not None), key))
            return self.get(key)


def ci_state(checks, statuses, workflows):
    """Classify complete current-head inventories without using a rollup verdict."""
    # Commit status history is newest-first; a newer success replaces an older
    # pending state for the same context. Workflow reruns retain their latest attempt.
    current_statuses = {}
    for status in statuses:
        context = status["context"]
        if context not in current_statuses or status["id"] > current_statuses[context]["id"]:
            current_statuses[context] = status
    current_workflows = {}
    for run in workflows:
        existing = current_workflows.get(run["id"])
        if existing is None or run["run_attempt"] > existing["run_attempt"]:
            current_workflows[run["id"]] = run
    runs = checks + list(current_workflows.values())
    states = [s["state"] for s in current_statuses.values()]
    if not runs and not states:
        return "unregistered"
    if any(r["status"] != "completed" or r["conclusion"] is None for r in runs):
        return "in_flight"
    if any(s not in {"success", "failure", "error"} for s in states):
        return "in_flight"
    if any(r["conclusion"] not in SUCCESS for r in runs) or any(s != "success" for s in states):
        return "failure"
    return "success"


def plan(previous, current):
    """Describe actionable changes while leaving readiness and mutations to owners."""
    reasons = []
    if previous is None:
        reasons.append("registered")
    elif previous["head"] != current["head"]:
        reasons.append("head_changed")
    if previous is None or previous["ci"] != current["ci"]:
        if current["ci"] in ("success", "failure"):
            reasons.append("ci_terminal")
    if current["currency"] == "conflict" and (previous is None or previous["currency"] != "conflict"):
        reasons.append("conflict")
    if previous is not None and previous["currency"] == "conflict" and current["currency"] != "conflict":
        reasons.append("conflict_resolved")
    if (previous is not None and current["ci"] in ("success", "failure")
            and current.get("inventory") != previous.get("inventory")):
        reasons.append("ci_evidence_changed")
    if previous is not None and current["feedback"] != previous["feedback"]:
        reasons.append("feedback_changed")
    if current["state"] != "OPEN":
        reasons.append("pr_terminal")
        action = "stop"
    elif current["currency"] == "conflict":
        action = "resolve_conflict"
    elif current["ci"] in ("in_flight", "unregistered"):
        action = "observe_current_head"
    elif current["currency"] == "update_candidate":
        action = "reread_before_update"
    elif current["ci"] == "failure":
        action = "diagnose_ci"
    else:
        action = "owner_gate"
    return {"reasons": sorted(reasons), "head": current["head"], "next_action": action}


class GitHub:
    """Read authoritative GitHub evidence through an explicit read-only gh route."""

    def __init__(self, host, repository, number, owner, owner_session=None):
        identity(host, repository, number)
        self.host, self.repository, self.number, self.owner = host, repository, number, owner
        self.owner_session = owner_session

    def api(self, endpoint, paginated=False):
        """Read every endpoint page, failing closed on command or JSON errors."""
        command = ["gh", "api", "--hostname", self.host, "--method", "GET"]
        if paginated:
            command += ["--paginate", "--slurp"]
        command.append(f"/repos/{self.repository}/{endpoint}")
        try:
            result = subprocess.run(command, check=True, capture_output=True, text=True, timeout=20)
            return json.loads(result.stdout)
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            # Do not persist returned server text or credential-command output.
            raise ObservationError(f"GitHub {endpoint.split('?')[0]} read unavailable ({type(error).__name__})") from error

    def pages(self, endpoint, field=None):
        """Flatten slurped API pages and reject malformed or truncated inventories."""
        pages = self.api(endpoint, True)
        if not isinstance(pages, list) or not pages:
            raise ObservationError("missing paginated inventory")
        records = []
        for page in pages:
            values = page.get(field) if field and isinstance(page, dict) else page if not field else None
            if not isinstance(values, list) or any(not isinstance(value, dict) for value in values):
                raise ObservationError("malformed paginated inventory")
            records.extend(values)
        if field:
            counts = [page.get("total_count") for page in pages]
            if any(not isinstance(count, int) or count < 0 for count in counts) or len(records) < max(counts):
                raise ObservationError("incomplete paginated inventory")
        return records

    def observe(self):
        """Collect a stable-head snapshot; a concurrent head/base move is unknown."""
        try:
            pr = self.api(f"pulls/{self.number}")
            head, base = pr["head"]["sha"], pr["base"]
            state = "MERGED" if pr["merged"] else str(pr["state"]).upper()
            if state not in ("OPEN", "CLOSED", "MERGED") or not head or not base["ref"] or not base["sha"]:
                raise ObservationError("invalid PR identity/state")
            checks, statuses, workflows, feedback = [], [], [], []
            if state == "OPEN":
                checks = self.pages(f"commits/{head}/check-runs?per_page=100", "check_runs")
                statuses = self.pages(f"commits/{head}/statuses?per_page=100")
                inventory = self.pages(f"actions/runs?head_sha={head}&per_page=100", "workflow_runs")
                workflows = [run for run in inventory if run["head_sha"] == head and
                    (not run["pull_requests"] or any(p["number"] == self.number for p in run["pull_requests"]))]
                for endpoint in (f"issues/{self.number}/comments?per_page=100",
                                 f"pulls/{self.number}/reviews?per_page=100",
                                 f"pulls/{self.number}/comments?per_page=100"):
                    for item in self.pages(endpoint):
                        # Only the registered session's own conversation prose
                        # is irrelevant. A human using the same login or another
                        # agent's review still changes the feedback inventory.
                        own_reply = (endpoint.startswith("issues/") and self.owner_session
                            and item["user"]["login"].lower() == self.owner.lower()
                            and f"\nSession: {self.owner_session}" in item.get("body", "")
                            and "\nHarness: Omp " in item.get("body", ""))
                        if not own_reply:
                            feedback.append([endpoint.split("?")[0], item["id"],
                                item.get("updated_at", item.get("submitted_at")), item.get("state"),
                                hashlib.sha256(item.get("body", "").encode()).hexdigest()])
            final = self.api(f"pulls/{self.number}")
            if (final["head"]["sha"] != head or final["base"] != base
                    or final["state"] != pr["state"] or final["merged"] != pr["merged"]):
                raise ObservationError("PR changed during observation; discard inventory")
            merge_state = final["mergeable_state"]
            currency = ("conflict" if merge_state == "dirty" or final["mergeable"] is False else
                        "current" if merge_state in ("clean", "unstable") else "update_candidate")
            inventory = {
                "checks": sorted([[run["id"], run["status"], run["conclusion"]] for run in checks]),
                "statuses": sorted([[status["id"], status["context"], status["state"]] for status in statuses]),
                "workflows": sorted([[run["id"], run["run_attempt"], run["status"], run["conclusion"]]
                                     for run in workflows]),
            }
            return {"head": head, "base": base["ref"], "base_sha": base["sha"], "state": state,
                    "currency": currency, "ci": ci_state(checks, statuses, workflows),
                    "inventory": inventory,
                    "feedback": sorted(feedback, key=lambda value: (value[0], value[1]))}
        except (KeyError, TypeError, AttributeError) as error:
            raise ObservationError("malformed authoritative GitHub evidence") from error


def reconcile(ledger, key, github, clock=time.time):
    """Reconcile one shadow record and discard evidence from a lost lease."""
    writer = str(uuid.uuid4())
    epoch = ledger.acquire(key, writer, clock())
    if epoch is None:
        return ledger.get(key)
    try:
        snapshot = github.observe()
    except ObservationError as error:
        return ledger.finish(key, writer, epoch, clock(), error=str(error))
    return ledger.finish(key, writer, epoch, clock(), snapshot=snapshot)


def main():
    """Expose explicit opt-in shadow observation, never install a live watch."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="owner-only ledger outside Git")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    register.add_argument("--host", default="github.com")
    register.add_argument("--repository", required=True)
    register.add_argument("--number", required=True, type=int)
    register.add_argument("--owner", required=True, help="GitHub login of the author")
    register.add_argument("--context", required=True, type=Path, help="nonsecret task context JSON")
    commands.add_parser("reconcile", help="observe each due shadow record once")
    commands.add_parser("list")
    for command in ("stop", "hold", "release"):
        control = commands.add_parser(command)
        control.add_argument("identity")
        control.add_argument("--reason", required=True)
    args = parser.parse_args()
    ledger = Ledger(args.database)
    try:
        if args.command == "register":
            output = ledger.register(args.host, args.repository, args.number, args.owner,
                                     json.loads(args.context.read_text()), time.time())
        elif args.command == "list":
            output = [dict(row) for row in ledger.db.execute("SELECT * FROM records ORDER BY identity")]
        elif args.command == "reconcile":
            output = []
            for key in ledger.due(time.time()):
                row = ledger.get(key)
                try:
                    source = GitHub(row["host"], row["repository"], row["number"], row["owner"],
                                    json.loads(row["context"]).get("session"))
                    result = reconcile(ledger, key, source)
                    output.append(result)
                except Fenced:
                    output.append({"identity": key, "result": "fenced; no observation committed"})
        else:
            output = ledger.control(args.identity, args.command, args.reason, time.time())
        print(json.dumps(output, indent=2, sort_keys=True))
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
