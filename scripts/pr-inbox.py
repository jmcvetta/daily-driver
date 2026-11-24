#!/usr/bin/env python3
"""Manage a durable opt-in owner inbox without GitHub mutation or takeover.

Receipt acknowledgments here are transport evidence, not CI/readiness evidence.
The consumer still needs a fresh GitHub read before acknowledging work complete.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sqlite3
import time


class Inbox:
    """Serialize generation delivery and stop fences across Omp/host processes."""

    def __init__(self, path):
        self.path = Path(path).expanduser().absolute()
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        if self.path.stat().st_mode & 0o077:
            raise ValueError("inbox database must be owner-only")
        self.db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        with self.transaction():
            version = self.db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ValueError("unsupported inbox schema")
            self.db.execute("""CREATE TABLE IF NOT EXISTS owners (
                session TEXT PRIMARY KEY, file TEXT NOT NULL, cwd TEXT NOT NULL,
                provider TEXT NOT NULL, model TEXT NOT NULL, effort TEXT NOT NULL,
                process TEXT NOT NULL, heartbeat REAL NOT NULL)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS deliveries (
                identity TEXT PRIMARY KEY, session TEXT NOT NULL, generation INTEGER NOT NULL,
                fence INTEGER NOT NULL DEFAULT 1, payload TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('pending','admitted','received','stopped')),
                held TEXT, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL,
                admission TEXT, receipt REAL, last_error TEXT)""")
            self.db.execute("PRAGMA user_version=1")

    @contextmanager
    def transaction(self):
        """Acquire atomic cross-process ownership without holding network work."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def close(self):
        """Close this handle without changing durable deliveries."""
        self.db.close()

    def enqueue(self, identity, session, generation, payload, now=None):
        """Coalesce newer generations; duplicate/older hints cannot replay receipt."""
        now = time.time() if now is None else now
        if not identity or not session or not isinstance(generation, int) or generation <= 0:
            raise ValueError("identity, session and positive generation are required")
        if not isinstance(payload, dict) or not payload:
            raise ValueError("nonempty task context payload is required")
        with self.transaction():
            old = self.db.execute("SELECT * FROM deliveries WHERE identity=?", (identity,)).fetchone()
            if old:
                if old["session"] != session:
                    raise ValueError("delivery identity already belongs to another owner")
                if old["status"] == "stopped" or old["generation"] >= generation:
                    return dict(old)
                self.db.execute("""UPDATE deliveries SET generation=?,fence=fence+1,payload=?,
                    status='pending',attempts=0,next_attempt=?,admission=NULL,receipt=NULL,last_error=NULL
                    WHERE identity=?""", (generation, json.dumps(payload), now, identity))
            else:
                self.db.execute("""INSERT INTO deliveries
                    (identity,session,generation,payload,status,next_attempt) VALUES (?,?,?,?,'pending',?)""",
                    (identity, session, generation, json.dumps(payload), now))
            return self.get(identity)

    def get(self, identity):
        """Read one durable delivery for tooling and isolated evidence."""
        row = self.db.execute("SELECT * FROM deliveries WHERE identity=?", (identity,)).fetchone()
        if row is None:
            raise ValueError("delivery is not registered")
        return dict(row)

    def stop(self, identity):
        """Fence pending/queued receipt work before the caller's stop-time push."""
        with self.transaction():
            self.get(identity)
            self.db.execute("""UPDATE deliveries SET status='stopped',fence=fence+1,
                admission=NULL,next_attempt=0 WHERE identity=?""", (identity,))
            return self.get(identity)

    def hold(self, identity, reason):
        """Fence delivery admission and retain an explicit hold across generations."""
        if not reason.strip():
            raise ValueError("hold reason must be nonempty")
        with self.transaction():
            self.get(identity)
            self.db.execute("""UPDATE deliveries SET held=?,fence=fence+1,admission=NULL,
                status=CASE WHEN status='stopped' THEN status ELSE 'pending' END WHERE identity=?""",
                (reason, identity))
            return self.get(identity)

    def release(self, identity):
        """Release a hold only; never clear a stopped delivery or restart its owner."""
        with self.transaction():
            row = self.get(identity)
            if row["status"] == "stopped":
                raise ValueError("hold release cannot clear a stop")
            self.db.execute("""UPDATE deliveries SET held=NULL,fence=fence+1,attempts=0,
                next_attempt=?,admission=NULL WHERE identity=?""", (time.time(), identity))
            return self.get(identity)


def main():
    """Expose opt-in durable transport controls without a live-watch installer."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    subcommands = parser.add_subparsers(dest="command", required=True)
    enqueue = subcommands.add_parser("enqueue")
    enqueue.add_argument("identity")
    enqueue.add_argument("--session", required=True)
    enqueue.add_argument("--generation", type=int, required=True)
    enqueue.add_argument("--context", type=Path, required=True)
    for command in ("get", "stop", "release"):
        subcommands.add_parser(command).add_argument("identity")
    hold = subcommands.add_parser("hold")
    hold.add_argument("identity")
    hold.add_argument("--reason", required=True)
    args = parser.parse_args()
    inbox = Inbox(args.database)
    try:
        if args.command == "enqueue":
            result = inbox.enqueue(args.identity, args.session, args.generation, json.loads(args.context.read_text()))
        elif args.command == "stop":
            result = inbox.stop(args.identity)
        elif args.command == "hold":
            result = inbox.hold(args.identity, args.reason)
        elif args.command == "release":
            result = inbox.release(args.identity)
        else:
            result = inbox.get(args.identity)
        print(json.dumps(result, sort_keys=True))
    finally:
        inbox.close()


if __name__ == "__main__":
    main()
