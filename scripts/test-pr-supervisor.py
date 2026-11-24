#!/usr/bin/env python3
"""Protect shadow consumers from duplicate records, stale writers and false CI.

These are product tests of the shipped shadow ledger/CLI, not tests of checks.
They never contact GitHub or activate an agent. Delivery and cutover are not
implemented by the shadow consumer and are not represented as passing coverage.
"""
from concurrent.futures import ThreadPoolExecutor
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts/pr-supervisor.py"
SPEC = importlib.util.spec_from_file_location("pr_supervisor", SCRIPT)
SUPERVISOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPERVISOR)


def snapshot(**changes):
    """Create authoritative normalized evidence for a deterministic ledger trace."""
    value = {"head": "a" * 40, "base": "release", "base_sha": "b" * 40,
             "state": "OPEN", "currency": "current", "ci": "success", "feedback": [],
             "inventory": {"checks": [[1, "completed", "success"]], "statuses": [], "workflows": []}}
    value.update(changes)
    return value


def check(identifier=1, status="completed", conclusion="success"):
    """Describe an actual check-run response shape used by the consumer."""
    return {"id": identifier, "status": status, "conclusion": conclusion}


def workflow(identifier=1, attempt=1, head="a" * 40, prs=None, **changes):
    """Describe a same-head workflow, including rerun and PR identity."""
    return {**check(identifier, **changes), "run_attempt": attempt,
            "head_sha": head, "pull_requests": [] if prs is None else [{"number": n} for n in prs]}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "ledger.sqlite"
        self.ledger = SUPERVISOR.Ledger(self.path)
        self.addCleanup(lambda: self.ledger.close())
        self.key = self.ledger.register("GitHub.COM", "Example/Project", 7, "owner",
            {"issue": 1038, "session": "session-a", "branch": "task"}, 0)["identity"]

    def finish(self, value, now=0):
        epoch = self.ledger.acquire(self.key, "writer", now)
        self.assertIsNotNone(epoch)
        return self.ledger.finish(self.key, "writer", epoch, now, snapshot=value)

    def test_concurrent_registration_preserves_one_owner_context(self):
        def register(index):
            ledger = SUPERVISOR.Ledger(self.path)
            try:
                return ledger.register("github.com", "example/project", 7, f"owner-{index}",
                                       {"session": str(index)}, index)
            finally:
                ledger.close()
        with ThreadPoolExecutor(max_workers=8) as workers:
            records = list(workers.map(register, range(16)))
        self.assertEqual({r["identity"] for r in records}, {self.key})
        self.assertEqual({r["owner"] for r in records}, {"owner"})
        self.assertEqual(self.ledger.db.execute("SELECT count(*) FROM records").fetchone()[0], 1)
        self.assertEqual(json.loads(self.ledger.get(self.key)["context"])["session"], "session-a")

    def test_identity_distinguishes_hosts_and_repositories(self):
        self.assertNotEqual(self.key, SUPERVISOR.identity("enterprise.example", "example/project", 7))
        self.assertNotEqual(self.key, SUPERVISOR.identity("github.com", "another/project", 7))
        for invalid in ("https://github.com", "-host", "host/other", "host\n"):
            with self.assertRaises(ValueError):
                SUPERVISOR.identity(invalid, "example/project", 7)

    def test_one_writer_and_expired_lease_is_fenced(self):
        first = self.ledger.acquire(self.key, "first", 0)
        self.assertIsNone(self.ledger.acquire(self.key, "second", 1))
        self.assertIsNone(self.ledger.acquire(self.key, "first", 1))
        second = self.ledger.acquire(self.key, "second", SUPERVISOR.LEASE_SECONDS)
        self.assertGreater(second, first)
        with self.assertRaises(SUPERVISOR.Fenced):
            self.ledger.finish(self.key, "first", first, SUPERVISOR.LEASE_SECONDS, snapshot=snapshot())
        self.ledger.finish(self.key, "second", second, SUPERVISOR.LEASE_SECONDS, snapshot=snapshot())

    def test_expiry_without_replacement_still_fences(self):
        epoch = self.ledger.acquire(self.key, "first", 0)
        with self.assertRaises(SUPERVISOR.Fenced):
            self.ledger.finish(self.key, "first", epoch, SUPERVISOR.LEASE_SECONDS, snapshot=snapshot())

    def test_stop_fences_in_flight_observation_and_reregistration(self):
        epoch = self.ledger.acquire(self.key, "first", 0)
        self.ledger.control(self.key, "stop", "explicit user stop", 1)
        with self.assertRaises(SUPERVISOR.Fenced):
            self.ledger.finish(self.key, "first", epoch, 2, snapshot=snapshot())
        row = self.ledger.register("github.com", "example/project", 7, "other", {"session": "other"}, 3)
        self.assertEqual(row["stopped"], "explicit user stop")
        self.assertIsNone(row["proposal"])
        self.assertEqual(self.ledger.due(9999), [])
        with self.assertRaises(ValueError):
            self.ledger.control(self.key, "release", "release unrelated hold", 4)

    def test_hold_survives_reopen_and_release_uses_same_identity(self):
        epoch = self.ledger.acquire(self.key, "first", 0)
        self.ledger.control(self.key, "hold", "owner hold", 1)
        with self.assertRaises(SUPERVISOR.Fenced):
            self.ledger.finish(self.key, "first", epoch, 2, snapshot=snapshot())
        other = SUPERVISOR.Ledger(self.path)
        try:
            self.assertEqual(other.due(1000), [])
            self.assertEqual(other.get(self.key)["held"], "owner hold")
            released = other.control(self.key, "release", "explicit release", 3)
            self.assertEqual(released["identity"], self.key)
            self.assertEqual(other.due(3), [self.key])
        finally:
            other.close()

    def test_duplicate_observations_do_not_create_new_generations(self):
        first = self.finish(snapshot())
        again = self.finish(snapshot(), 120)
        self.assertEqual(first["generation"], again["generation"])
        self.assertEqual(first["proposal"], again["proposal"])
        self.assertEqual(again["next_due"], 240)

    def test_recovery_reports_missed_observation_gap_not_continuity(self):
        self.finish(snapshot())
        recovered = self.finish(snapshot(), 600)
        self.assertEqual((recovered["gap_start"], recovered["gap_end"]), (120, 600))
        later = self.finish(snapshot(), 720)
        self.assertEqual((later["gap_start"], later["gap_end"]), (120, 600))
        self.assertEqual(later["generation"], recovered["generation"])

    def test_credentials_failure_is_durable_and_recovery_is_changed(self):
        self.finish(snapshot())
        epoch = self.ledger.acquire(self.key, "writer", 120)
        failed = self.ledger.finish(self.key, "writer", epoch, 120, error="credentials unavailable")
        self.assertEqual(failed["degraded"], "credentials unavailable")
        self.assertIsNone(failed["gap_end"])
        epoch = self.ledger.acquire(self.key, "writer", 240)
        duplicate = self.ledger.finish(self.key, "writer", epoch, 240, error="credentials unavailable")
        self.assertEqual(failed["generation"], duplicate["generation"])
        restored = self.finish(snapshot(), 360)
        self.assertIsNone(restored["degraded"])
        self.assertEqual((restored["gap_start"], restored["gap_end"]), (120, 360))
        self.assertIn("observation_recovered", json.loads(restored["proposal"])["reasons"])

    def test_terminal_records_clear_proposals_and_stop_reconciliation(self):
        for state in ("MERGED", "CLOSED"):
            with self.subTest(state=state):
                other = SUPERVISOR.Ledger(Path(self.temporary.name) / f"{state}.sqlite")
                try:
                    key = other.register("github.com", "example/project", 9, "owner", {"issue": 9}, 0)["identity"]
                    epoch = other.acquire(key, "writer", 0)
                    result = other.finish(key, "writer", epoch, 0, snapshot=snapshot(state=state))
                    self.assertEqual(result["stopped"], state.lower())
                    self.assertIsNone(result["proposal"])
                    self.assertIsNone(result["lease_owner"])
                    self.assertEqual(other.due(1000), [])
                finally:
                    other.close()

    def test_database_refuses_nonprivate_or_symlinked_storage(self):
        public = Path(self.temporary.name) / "public.sqlite"
        public.touch(mode=0o644)
        with self.assertRaises(ValueError):
            SUPERVISOR.Ledger(public)
        link = Path(self.temporary.name) / "link.sqlite"
        link.symlink_to(self.path)
        with self.assertRaises(OSError):
            SUPERVISOR.Ledger(link)


class InventoryTests(unittest.TestCase):
    def test_empty_is_unregistered(self):
        self.assertEqual(SUPERVISOR.ci_state([], [], []), "unregistered")

    def test_workflow_only_in_flight_overrides_successful_checks(self):
        for status in ("queued", "waiting", "in_progress", "requested", "unknown", None):
            with self.subTest(status=status):
                self.assertEqual(SUPERVISOR.ci_state([check()], [], [workflow(status=status, conclusion=None)]), "in_flight")

    def test_completed_without_conclusion_is_not_terminal(self):
        self.assertEqual(SUPERVISOR.ci_state([check(conclusion=None)], [], []), "in_flight")

    def test_latest_status_context_and_workflow_attempt_win(self):
        statuses = [{"id": 1, "context": "test", "state": "pending"},
                    {"id": 2, "context": "test", "state": "success"}]
        runs = [workflow(attempt=1, status="in_progress", conclusion=None), workflow(attempt=2)]
        self.assertEqual(SUPERVISOR.ci_state([], statuses, runs), "success")
        statuses.append({"id": 3, "context": "test", "state": "failure"})
        self.assertEqual(SUPERVISOR.ci_state([], statuses, runs), "failure")

    def test_new_head_and_conflict_recovery_are_actionable(self):
        previous = snapshot(currency="conflict", ci="in_flight")
        current = snapshot(head="c" * 40)
        proposal = SUPERVISOR.plan(previous, current)
        self.assertTrue({"head_changed", "conflict_resolved", "ci_terminal"} <= set(proposal["reasons"]))
        self.assertEqual(SUPERVISOR.plan(current, current)["reasons"], [])

    def test_changed_terminal_failure_evidence_is_not_lost(self):
        previous = snapshot(ci="failure")
        current = snapshot(ci="failure", inventory={"checks": [[2, "completed", "failure"]]})
        self.assertIn("ci_evidence_changed", SUPERVISOR.plan(previous, current)["reasons"])


FAKE_GH = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert args[:3] == ["api", "--hostname", "enterprise.example"], args
state_path = Path(os.environ["SHADOW_FIXTURE"])
state = json.loads(state_path.read_text())
state["calls"].append(args)
if args[3] == "graphql":
    assert "--paginate" in args and "--slurp" in args
    assert "mutation" not in args[args.index("-f") + 1]
    empty = {"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[],"pageInfo":{"hasNextPage":False,"endCursor":None}}}}}}
    value = state.get("threads", [empty])
    state_path.write_text(json.dumps(state))
    print(json.dumps(value))
    raise SystemExit(0)
assert args[3:5] == ["--method", "GET"], args
endpoint = args[-1]
if endpoint.endswith("/pulls/7"):
    sequence = state["pr"]
    value = sequence.pop(0) if len(sequence) > 1 else sequence[0]
else:
    value = state["responses"][endpoint.split("/repos/example/project/")[1]]
state_path.write_text(json.dumps(state))
print(json.dumps(value))
'''


class GitHubConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        fake = self.base / "gh"
        fake.write_text(FAKE_GH)
        fake.chmod(0o755)
        self.fixture = self.base / "fixture.json"
        self.pr = {"head": {"sha": "a" * 40}, "base": {"ref": "release", "sha": "b" * 40},
                   "state": "open", "merged": False, "mergeable": True, "mergeable_state": "clean"}
        self.state = {"pr": [self.pr], "calls": [], "responses": {
            f"compare/{'b' * 40}...{'a' * 40}": {"merge_base_commit": {"sha": "b" * 40}, "behind_by": 0},
            f"commits/{'a' * 40}/check-runs?per_page=100": [{"total_count": 1, "check_runs": [check()]}],
            f"commits/{'a' * 40}/statuses?per_page=100": [[]],
            f"actions/runs?head_sha={'a' * 40}&per_page=100": [{"total_count": 0, "workflow_runs": []}],
            "issues/7/comments?per_page=100": [[]], "pulls/7/reviews?per_page=100": [[]],
            "pulls/7/comments?per_page=100": [[]]}}
        self.environment = {**os.environ, "PATH": str(self.base) + os.pathsep + os.environ["PATH"],
                            "SHADOW_FIXTURE": str(self.fixture)}

    def observe(self):
        self.fixture.write_text(json.dumps(self.state))
        from unittest.mock import patch
        with patch.dict(os.environ, self.environment, clear=True):
            return SUPERVISOR.GitHub("enterprise.example", "example/project", 7, "owner", "session-a").observe()

    def test_paginated_sources_and_actual_base_are_consumed_read_only(self):
        self.state["responses"][f"commits/{'a' * 40}/check-runs?per_page=100"] = [
            {"total_count": 2, "check_runs": [check()]},
            {"total_count": 2, "check_runs": [check(2)]}]
        result = self.observe()
        self.assertEqual(result["base"], "release")
        self.assertEqual(len(result["inventory"]["checks"]), 2)
        calls = json.loads(self.fixture.read_text())["calls"]
        self.assertEqual(len(calls), 12)
        self.assertTrue(any("--paginate" in call and "--slurp" in call for call in calls))
        self.assertFalse(any("update-branch" in call for call in calls))

    def test_only_matching_head_and_pr_workflows_affect_ci(self):
        runs = [workflow(prs=[8], status="in_progress", conclusion=None),
                workflow(identifier=2, head="d" * 40, status="in_progress", conclusion=None), workflow(identifier=3)]
        self.state["responses"][f"actions/runs?head_sha={'a' * 40}&per_page=100"] = [{"total_count": 3, "workflow_runs": runs}]
        self.assertEqual(self.observe()["ci"], "success")
        runs.append(workflow(identifier=4, prs=[7], status="queued", conclusion=None))
        self.state["responses"][f"actions/runs?head_sha={'a' * 40}&per_page=100"][0]["total_count"] = 4
        self.assertEqual(self.observe()["ci"], "in_flight")

    def test_head_change_discards_all_old_head_evidence(self):
        changed = copy.deepcopy(self.pr)
        changed["head"]["sha"] = "c" * 40
        self.state["pr"] = [self.pr, changed]
        with self.assertRaisesRegex(SUPERVISOR.ObservationError, "changed during ancestry"):
            self.observe()

    def test_incomplete_and_malformed_inventories_are_unknown(self):
        endpoint = f"commits/{'a' * 40}/check-runs?per_page=100"
        for pages in ([], [{"total_count": 2, "check_runs": [check()]}], [{"check_runs": None}], [{}]):
            with self.subTest(pages=pages):
                self.state["responses"][endpoint] = pages
                with self.assertRaises(SUPERVISOR.ObservationError):
                    self.observe()

    def test_own_agent_reply_is_silent_but_same_login_human_and_review_are_not(self):
        own = {"id": 1, "user": {"login": "owner"}, "updated_at": "now",
               "body": "Reply\n---\nModel: model\nHarness: Omp 19.1.1\nSession: session-a"}
        human = {**own, "id": 2, "body": "Keep this on hold"}
        peer = {**own, "id": 3, "body": own["body"].replace("session-a", "session-b")}
        self.state["responses"]["issues/7/comments?per_page=100"] = [[own, human, peer]]
        self.state["responses"]["pulls/7/reviews?per_page=100"] = [[{**own, "state": "CHANGES_REQUESTED"}]]
        feedback = self.observe()["feedback"]
        self.assertEqual([(item[0], item[1]) for item in feedback],
            [("issues/7/comments", 2), ("issues/7/comments", 3), ("pulls/7/reviews", 1)])

    def test_masked_currency_uses_ancestry(self):
        endpoint = f"compare/{'b' * 40}...{'a' * 40}"
        for status in ("behind", "draft", "blocked", "unknown", None):
            self.pr["mergeable_state"] = status
            self.assertEqual(self.observe()["currency"], "current")
            self.state["responses"][endpoint] = {"merge_base_commit": {"sha": "c" * 40}, "behind_by": 1}
            self.assertEqual(self.observe()["currency"], "update_candidate")
            self.state["responses"][endpoint] = {"merge_base_commit": {"sha": "b" * 40}, "behind_by": 0}

    def test_inconsistent_comparison_is_unknown(self):
        self.state["responses"][f"compare/{'b' * 40}...{'a' * 40}"] = {
            "merge_base_commit": {"sha": "b" * 40}, "behind_by": 1}
        with self.assertRaisesRegex(SUPERVISOR.ObservationError, "inconsistent"):
            self.observe()

    def test_cli_registers_and_observes_without_installation_or_wakes(self):
        self.fixture.write_text(json.dumps(self.state))
        context = self.base / "context.json"
        context.write_text(json.dumps({"issue": 1038, "session": "session-a", "branch": "task"}))
        prefix = [sys.executable, str(SCRIPT), "--database", str(self.base / "cli.sqlite")]
        subprocess.run(prefix + ["register", "--host", "enterprise.example", "--repository", "example/project",
            "--number", "7", "--owner", "owner", "--context", str(context)], check=True, capture_output=True,
            env=self.environment, text=True)
        run = subprocess.run(prefix + ["reconcile"], check=True, capture_output=True, env=self.environment, text=True)
        rows = json.loads(run.stdout)
        self.assertEqual(rows[0]["mode"], "shadow")
        self.assertEqual(json.loads(rows[0]["observed"])["ci"], "success")
        self.assertEqual(len(json.loads(self.fixture.read_text())["calls"]), 12)
        repeated = subprocess.run(prefix + ["reconcile"], check=True, capture_output=True, env=self.environment, text=True)
        self.assertEqual(json.loads(repeated.stdout), [])

    def test_review_thread_state_is_read_through_all_pages(self):
        def page(identifier, resolved, more):
            return {"data":{"repository":{"pullRequest":{"reviewThreads":{
                "nodes":[{"id":identifier,"isResolved":resolved,"isOutdated":False}],
                "pageInfo":{"hasNextPage":more,"endCursor":"cursor" if more else None}}}}}}
        self.state["threads"] = [page("thread-a", False, True), page("thread-b", True, False)]
        observed = self.observe()
        self.assertIn(["threads", "thread-a", False, False], observed["feedback"])
        self.assertIn(["threads", "thread-b", True, False], observed["feedback"])
        self.state["threads"] = [page("thread-a", False, True)]
        with self.assertRaisesRegex(SUPERVISOR.ObservationError, "pagination"):
            self.observe()

    def test_new_failure_wakes_owner_while_other_workflow_stays_in_flight(self):
        self.state["responses"][f"commits/{'a' * 40}/check-runs?per_page=100"] = [
            {"total_count":1,"check_runs":[check(conclusion="failure")]}]
        self.state["responses"][f"actions/runs?head_sha={'a' * 40}&per_page=100"] = [
            {"total_count":1,"workflow_runs":[workflow(status="in_progress",conclusion=None)]}]
        observed = self.observe()
        self.assertEqual(observed["ci"], "in_flight")
        proposal = SUPERVISOR.plan(snapshot(ci="in_flight", failures=[]), observed)
        self.assertIn("ci_failure", proposal["reasons"])
        self.assertEqual(proposal["next_action"], "diagnose_ci")

    def test_boolean_inventory_count_is_not_passing_evidence(self):
        self.state["responses"][f"commits/{'a' * 40}/check-runs?per_page=100"] = [
            {"total_count":True,"check_runs":[check()]}]
        with self.assertRaises(SUPERVISOR.ObservationError):
            self.observe()


if __name__ == "__main__":
    unittest.main()
