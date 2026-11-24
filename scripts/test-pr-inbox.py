#!/usr/bin/env python3
"""Protect durable inbox consumers against duplicate, stale and stolen work."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("pr_inbox", ROOT / "scripts/pr-inbox.py")
INBOX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INBOX)
HOST_SPEC = importlib.util.spec_from_file_location("pr_inbox_host", ROOT / "scripts/pr-inbox-host.py")
HOST = importlib.util.module_from_spec(HOST_SPEC)
HOST_SPEC.loader.exec_module(HOST)
IDENTITY = "isolated.example/fixture/project/7"


class InboxTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "inbox.sqlite"
        self.inbox = INBOX.Inbox(self.path)
        self.addCleanup(self.inbox.close)
        self.row = self.inbox.enqueue(IDENTITY, "owner", 1, {"issue": 7}, now=0)

    def test_concurrent_generation_delivery_retains_newest_once(self):
        def enqueue(generation):
            inbox = INBOX.Inbox(self.path)
            try:
                return inbox.enqueue(IDENTITY, "owner", generation, {"generation": generation}, now=0)
            finally:
                inbox.close()
        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(enqueue, [5, 2, 3, 1, 5, 4, 2, 5]))
        self.assertEqual(self.inbox.get(IDENTITY)["generation"], 5)
        self.assertEqual(self.inbox.db.execute("SELECT count(*) FROM deliveries").fetchone()[0], 1)

    def test_duplicate_and_old_generation_cannot_replay_received_work(self):
        self.inbox.db.execute("UPDATE deliveries SET status='received',receipt=5,attempts=1")
        same = self.inbox.enqueue(IDENTITY, "owner", 1, {"different": True}, now=6)
        self.assertEqual((same["status"], same["receipt"], same["attempts"]), ("received", 5, 1))
        newer = self.inbox.enqueue(IDENTITY, "owner", 2, {"issue": 7}, now=7)
        self.assertEqual((newer["status"], newer["attempts"], newer["receipt"]), ("pending", 0, None))
        self.assertGreater(newer["fence"], same["fence"])
        old = self.inbox.enqueue(IDENTITY, "owner", 1, {"issue": 7}, now=8)
        self.assertEqual(old, newer)

    def test_another_session_cannot_adopt_same_delivery(self):
        with self.assertRaisesRegex(ValueError, "another owner"):
            self.inbox.enqueue(IDENTITY, "other", 2, {"issue": 7}, now=1)
        self.assertEqual(self.inbox.get(IDENTITY), self.row)

    def test_stop_invalidates_admission_and_survives_new_generation(self):
        self.inbox.db.execute("UPDATE deliveries SET status='admitted',admission='token'")
        stopped = self.inbox.stop(IDENTITY)
        self.assertEqual(stopped["status"], "stopped")
        self.assertIsNone(stopped["admission"])
        self.assertGreater(stopped["fence"], self.row["fence"])
        self.assertEqual(self.inbox.enqueue(IDENTITY, "owner", 99, {"issue": 7}), stopped)
        self.assertEqual(HOST.pass_once(self.inbox, "unused-omp"), [])
        with self.assertRaises(ValueError):
            self.inbox.release(IDENTITY)

    def test_hold_survives_reregistration_and_reopen(self):
        self.inbox.hold(IDENTITY, "explicit hold")
        self.inbox.enqueue(IDENTITY, "owner", 2, {"issue": 7})
        self.assertEqual(HOST.pass_once(self.inbox, "unused-omp"), [])
        other = INBOX.Inbox(self.path)
        try:
            row = other.get(IDENTITY)
            self.assertEqual(row["held"], "explicit hold")
            released = other.release(IDENTITY)
            self.assertIsNone(released["held"])
            self.assertEqual(released["status"], "pending")
            self.assertGreater(released["fence"], row["fence"])
        finally:
            other.close()

    def test_missing_owner_context_is_durable_degraded_not_a_takeover(self):
        with patch.object(HOST, "activate") as activate:
            result = HOST.pass_once(self.inbox, "unused-omp")
        activate.assert_not_called()
        self.assertEqual(result, [{"session": "owner", "outcome": "owner-context-unavailable"}])
        self.assertEqual(self.inbox.get(IDENTITY)["last_error"], "owner-context-unavailable")

    def owner(self, heartbeat=0):
        self.inbox.db.execute("""INSERT INTO owners
            (session,file,cwd,provider,model,effort,process,heartbeat) VALUES (?,?,?,?,?,?,?,?)""",
            ("owner", "/fixture/session.jsonl", self.temporary.name, "provider", "model", "high", "process", heartbeat))
        return dict(self.inbox.db.execute("SELECT * FROM owners").fetchone())

    def test_heartbeat_keeps_delivery_on_live_extension(self):
        self.owner(heartbeat=100)
        with patch.object(HOST.time, "time", return_value=101), patch.object(HOST, "activate") as activate:
            self.assertEqual(HOST.pass_once(self.inbox, "unused-omp"),
                             [{"session": "owner", "outcome": "live-extension-owner"}])
        activate.assert_not_called()

    def test_expired_owner_routes_through_exclusive_activation(self):
        self.owner()
        with patch.object(HOST, "activate", return_value="received") as activate:
            self.assertEqual(HOST.pass_once(self.inbox, "unused-omp"), [{"session": "owner", "outcome": "received"}])
        activate.assert_called_once()

    def test_held_or_unknown_native_session_never_spawns_owner(self):
        owner = self.owner()
        for answer in ({"held": ["owner"], "unknown": []}, {"held": [], "unknown": ["owner"]}):
            with self.subTest(answer=answer), patch.object(HOST.subprocess, "run",
                    return_value=subprocess.CompletedProcess([], 0, json.dumps(answer), "")), \
                    patch.object(HOST.subprocess, "Popen") as spawn:
                self.assertEqual(HOST.activate(self.inbox, owner, "omp"), "owner-held-or-unknown")
                spawn.assert_not_called()

    def test_failed_lease_probe_fails_closed_without_spawning(self):
        owner = self.owner()
        with patch.object(HOST.subprocess, "run", side_effect=subprocess.TimeoutExpired("omp", 15)), \
                patch.object(HOST.subprocess, "Popen") as spawn:
            result = HOST.pass_once(self.inbox, "omp")
        spawn.assert_not_called()
        self.assertEqual(result, [{"session": "owner", "outcome": "degraded:TimeoutExpired"}])
        self.assertEqual(self.inbox.get(IDENTITY)["last_error"], "degraded:TimeoutExpired")

    def test_retry_limit_and_future_deadline_do_not_launch_owner(self):
        self.owner()
        for attempts, deadline in ((5, 0), (1, 200)):
            with self.subTest(attempts=attempts):
                self.inbox.db.execute("UPDATE deliveries SET attempts=?,next_attempt=?", (attempts, deadline))
                with patch.object(HOST.time, "time", return_value=100), patch.object(HOST, "activate") as activate:
                    self.assertEqual(HOST.pass_once(self.inbox, "unused-omp"), [])
                activate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
