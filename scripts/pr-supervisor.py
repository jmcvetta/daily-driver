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
from urllib.parse import urlparse

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

    def control(self, key, operation, reason, now, persist=None):
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
            if persist is not None:
                persist(self.get(key))
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

    def finish(self, key, writer, epoch, now, snapshot=None, error=None, persist=None):
        """Commit one fenced observation, coalescing a proposal without delivery."""
        with self.transaction():
            record = self.get(key)
            if (record["epoch"] != epoch or record["lease_owner"] != writer
                    or record["lease_until"] <= now or record["stopped"] or record["held"]):
                raise Fenced("shadow observation lost its lease or was stopped/held")
            previous = json.loads(record["observed"]) if record["observed"] else None
            gap_start, gap_end = record["gap_start"], record["gap_end"]
            started = record["lease_until"] - LEASE_SECONDS
            if record["last_observed"] is not None and started > record["next_due"]:
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
                if record["last_observed"] is not None and started > record["next_due"]:
                    changed = True
                    proposal["reasons"] = sorted(set(proposal["reasons"] + ["supervision_gap"]))
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
                 gap_start, gap_end, now, started + INTERVAL, stopped, int(stopped is not None), key))
            if persist is not None:
                persist(self.get(key))
            return self.get(key)


def _current_ci(checks, statuses, workflows):
    """Normalize latest status contexts and workflow attempts consistently."""
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
    return checks + list(current_workflows.values()), list(current_statuses.values())


def ci_state(checks, statuses, workflows):
    """Classify complete current-head inventories without using a rollup verdict."""
    runs, statuses = _current_ci(checks, statuses, workflows)
    states = [s["state"] for s in statuses]
    if not runs and not states:
        return "unregistered"
    if any(r["status"] != "completed" or r["conclusion"] is None for r in runs):
        return "in_flight"
    if any(s not in {"success", "failure", "error"} for s in states):
        return "in_flight"
    if any(r["conclusion"] not in SUCCESS for r in runs) or any(s != "success" for s in states):
        return "failure"
    return "success"


def _ci_failures(checks, statuses, workflows):
    """Identify new failures even while other current-head work remains in flight."""
    runs, statuses = _current_ci(checks, statuses, workflows)
    failed = [f'run:{run["id"]}:{run.get("run_attempt", 0)}:{run["conclusion"]}'
              for run in runs if run["status"] == "completed" and run["conclusion"] is not None
              and run["conclusion"] not in SUCCESS]
    failed += [f'status:{status["context"]}:{status["id"]}:{status["state"]}'
               for status in statuses if status["state"] in ("failure", "error")]
    return sorted(failed)


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
    if current.get("failures") and (previous is None or current["failures"] != previous.get("failures")):
        reasons.append("ci_failure")
    if current["currency"] == "conflict" and (previous is None or previous["currency"] != "conflict"):
        reasons.append("conflict")
    if previous is not None and previous["currency"] == "conflict" and current["currency"] != "conflict":
        reasons.append("conflict_resolved")
    if (previous is not None and current["ci"] in ("success", "failure")
            and current.get("inventory") != previous.get("inventory")):
        reasons.append("ci_evidence_changed")
    if previous is not None and current["feedback"] != previous["feedback"]:
        reasons.append("feedback_changed")
    if previous is not None and current.get("metadata") != previous.get("metadata"):
        reasons.append("metadata_changed")
    if current["state"] != "OPEN":
        reasons.append("pr_terminal")
        action = "stop"
    elif current["currency"] == "conflict":
        action = "resolve_conflict"
    elif current.get("failures") or current["ci"] == "failure":
        action = "diagnose_ci"
    elif current["ci"] in ("in_flight", "unregistered"):
        action = "observe_current_head"
    elif current["currency"] == "update_candidate":
        action = "reread_before_update"
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
            if any(not isinstance(count, int) or isinstance(count, bool) or count < 0 for count in counts) or len(records) < max(counts):
                raise ObservationError("incomplete paginated inventory")
        return records

    def threads(self):
        """Read every review-thread state without fetching or persisting bodies."""
        query = """query($owner:String!,$name:String!,$number:Int!,$endCursor:String) {
          repository(owner:$owner,name:$name) { pullRequest(number:$number) {
            reviewThreads(first:100,after:$endCursor) {
              nodes { id isResolved isOutdated } pageInfo { hasNextPage endCursor }
            }
          } }
        }"""
        owner, name = self.repository.split("/")
        command = ["gh", "api", "--hostname", self.host, "graphql", "--paginate", "--slurp",
                   "-f", "query=" + query, "-F", "owner=" + owner, "-F", "name=" + name,
                   "-F", "number=" + str(self.number)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=20)
            pages = json.loads(result.stdout)
            if not isinstance(pages, list) or not pages:
                raise ObservationError("missing review-thread inventory")
            threads = []
            for index, page in enumerate(pages):
                if page.get("errors"):
                    raise ObservationError("review-thread read returned errors")
                collection = page["data"]["repository"]["pullRequest"]["reviewThreads"]
                if bool(collection["pageInfo"]["hasNextPage"]) != (index < len(pages) - 1):
                    raise ObservationError("incomplete review-thread pagination")
                for thread in collection["nodes"]:
                    if not isinstance(thread["isResolved"], bool) or not isinstance(thread["isOutdated"], bool):
                        raise ObservationError("invalid review-thread state")
                    threads.append(["threads", thread["id"], thread["isResolved"], thread["isOutdated"]])
            return threads
        except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as error:
            raise ObservationError("review-thread inventory unavailable") from error

    def observe_currency(self):
        """Read pinned ancestry independently of CI and bracket it with PR reads."""
        try:
            pr = self.api(f"pulls/{self.number}")
            def fields(value):
                if not isinstance(value["merged"], bool):
                    raise ObservationError("invalid PR merged state")
                state = "MERGED" if value["merged"] else value["state"].upper()
                head, base = value["head"]["sha"], value["base"]
                if (state not in ("OPEN", "CLOSED", "MERGED")
                        or not re.fullmatch(r"[0-9a-fA-F]{40}", head)
                        or not re.fullmatch(r"[0-9a-fA-F]{40}", base["sha"])
                        or not isinstance(base["ref"], str) or not base["ref"]):
                    raise ObservationError("invalid PR identity/state")
                return state, head, base["ref"], base["sha"]
            state, head, base, base_sha = fields(pr)
            ancestry = None
            currency = None
            if state == "OPEN":
                if pr["mergeable"] is False or pr["mergeable_state"] == "dirty":
                    currency = "conflict"
                elif pr["mergeable"] is not True:
                    raise ObservationError("PR conflict state is unavailable")
                else:
                    comparison = self.api(f"compare/{base_sha}...{head}")
                    merge_base = comparison["merge_base_commit"]["sha"]
                    behind = comparison["behind_by"]
                    if (not isinstance(merge_base, str)
                            or not re.fullmatch(r"[0-9a-fA-F]{40}", merge_base)
                            or not isinstance(behind, int) or isinstance(behind, bool) or behind < 0
                            or (merge_base.lower() == base_sha.lower()) != (behind == 0)
                            or (head.lower() == base_sha.lower() and behind != 0)):
                        raise ObservationError("inconsistent ancestry comparison")
                    ancestry = {"merge_base_sha": merge_base, "behind_by": behind}
                    currency = "current" if behind == 0 else "update_candidate"
            final = self.api(f"pulls/{self.number}")
            if fields(final) != (state, head, base, base_sha):
                raise ObservationError("PR changed during ancestry comparison")
            if state == "OPEN" and (final["mergeable"] is False or final["mergeable_state"] == "dirty"):
                currency, ancestry = "conflict", None
            elif state == "OPEN" and final["mergeable"] is not True:
                raise ObservationError("PR conflict state is unavailable")
            return {"head": head, "base": base, "base_sha": base_sha, "state": state,
                    "currency": currency, "ancestry": ancestry}
        except (KeyError, TypeError, AttributeError, ValueError) as error:
            raise ObservationError("malformed currency evidence") from error

    def observe(self):
        """Collect a stable-head snapshot; a concurrent head/base move is unknown."""
        try:
            currency_snapshot = self.observe_currency()
            pr = self.api(f"pulls/{self.number}")
            head, base = pr["head"]["sha"], pr["base"]
            state = "MERGED" if pr["merged"] else str(pr["state"]).upper()
            if (head, base["ref"], base["sha"], state) != (
                    currency_snapshot["head"], currency_snapshot["base"],
                    currency_snapshot["base_sha"], currency_snapshot["state"]):
                raise ObservationError("PR changed before inventory")
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
                feedback.extend(self.threads())
            final = self.api(f"pulls/{self.number}")
            if (final["head"]["sha"] != head or final["base"] != base
                    or final["state"] != pr["state"] or final["merged"] != pr["merged"]):
                raise ObservationError("PR changed during observation; discard inventory")
            inventory = {
                "checks": sorted([[run["id"], run["status"], run["conclusion"]] for run in checks]),
                "statuses": sorted([[status["id"], status["context"], status["state"]] for status in statuses]),
                "workflows": sorted([[run["id"], run["run_attempt"], run["status"], run["conclusion"]]
                                     for run in workflows]),
            }
            return {"head": head, "base": base["ref"], "base_sha": base["sha"], "state": state,
                    "currency": currency_snapshot["currency"], "ancestry": currency_snapshot["ancestry"],
                    "ci": ci_state(checks, statuses, workflows),
                    "inventory": inventory,
                    "failures": _ci_failures(checks, statuses, workflows),
                    "metadata": {"draft": final.get("draft", False),
                                 "labels": sorted(item["name"] for item in final.get("labels", [])),
                                 "reviewers": sorted(item["login"] for item in final.get("requested_reviewers", []))},
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
    parser.add_argument("--database", type=Path, help="owner-only ledger outside Git")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register")
    register.add_argument("--host", default="github.com")
    register.add_argument("--repository", required=True)
    register.add_argument("--number", required=True, type=int)
    register.add_argument("--owner", required=True, help="GitHub login of the author")
    register.add_argument("--context", required=True, type=Path, help="nonsecret task context JSON")
    currency = commands.add_parser("currency", help="read pinned PR ancestry without a ledger")
    currency.add_argument("--url", required=True)
    commands.add_parser("reconcile", help="observe each due shadow record once")
    commands.add_parser("list")
    for command in ("stop", "hold", "release"):
        control = commands.add_parser(command)
        control.add_argument("identity")
        control.add_argument("--reason", required=True)
    args = parser.parse_args()
    if args.command == "currency":
        parsed = urlparse(args.url)
        match = re.fullmatch(r"/([^/]+/[^/]+)/pull/([1-9][0-9]*)", parsed.path)
        if parsed.scheme != "https" or not parsed.hostname or parsed.query or parsed.fragment or not match:
            parser.error("currency requires an exact HTTPS PR URL")
        try:
            source = GitHub(parsed.hostname, match[1], int(match[2]), "")
            print(json.dumps(source.observe_currency(), sort_keys=True))
        except (ObservationError, ValueError) as error:
            parser.exit(1, f"currency observation failed: {error}\n")
        return
    if args.database is None:
        parser.error("--database is required for ledger commands")
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
