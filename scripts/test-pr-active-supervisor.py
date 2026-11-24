#!/usr/bin/env python3
"""Exercise active PR authority, fresh work acknowledgment and migration offline."""
from concurrent.futures import ThreadPoolExecutor
import copy
import fcntl
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("pr_active_supervisor", ROOT / "scripts/pr-active-supervisor.py")
ACTIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTIVE)
SERVICE_CONTROL = ACTIVE.service_control


def snapshot(**changes):
    """Provide an exact current-head authoritative inventory for fixture traces."""
    result = {"head": "a" * 40, "base": "release", "base_sha": "b" * 40,
              "state": "OPEN", "ci": "success", "currency": "current", "feedback": [],
              "inventory": {"checks": [[1, "completed", "success"]], "statuses": [], "workflows": []}}
    result.update(changes)
    return result


class Source:
    """Record consumer operations and advance a deterministic authoritative trace."""

    def __init__(self, *states):
        self.states = list(states or [snapshot()])
        self.reads = 0
        self.updates = []

    def observe(self):
        self.reads += 1
        value = self.states.pop(0) if len(self.states) > 1 else self.states[0]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)

    def update(self, head):
        self.updates.append(head)


class ActiveTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "supervisor.sqlite"
        self.now = 0
        self.actor = ACTIVE.ActiveSupervisor(self.path, clock=lambda: self.now)
        self.addCleanup(self.actor.close)
        self.context = {"session": "owner", "worktree": self.temporary.name, "branch": "task", "task": "issue://7"}
        self.key = self.actor.register("github.com", "example/project", 7, "author", self.context)["identity"]
        self.host_lock = open(str(self.path) + ".actor-lock", "r+")
        fcntl.flock(self.host_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.addCleanup(self.host_lock.close)
        control = patch.object(ACTIVE, "service_control", return_value=None)
        control.start()
        self.addCleanup(control.stop)

    def activate(self, source=None):
        source = source or Source()
        with patch.object(self.actor, "source", return_value=source):
            return self.actor.transfer(self.key, ["keep-current-7"], [], process_control=lambda *_args: None)

    def admit(self):
        self.actor.db.execute("UPDATE deliveries SET status='admitted',admission='delivery-token'")
        return self.actor.inbox.get(self.key)

    def test_transfer_without_a_running_lifecycle_host_keeps_old_authority(self):
        fcntl.flock(self.host_lock, fcntl.LOCK_UN)
        with self.assertRaisesRegex(RuntimeError, "controller is unavailable"):
            self.actor.transfer(self.key, ["old-service"], [], lambda *_args: self.fail("must not stop old service"))
        self.assertEqual(self.actor.status(self.key)["authority"]["state"], "shadow")

    def test_shadow_is_read_only_and_never_delivers(self):
        source = Source(snapshot(currency="update_candidate"))
        result = self.actor.reconcile(self.key, source)
        self.assertEqual(source.updates, [])
        self.assertIsNone(result["delivery"])
        self.assertEqual(result["authority"]["state"], "shadow")

    def test_current_head_ci_defers_all_server_updates(self):
        self.activate()
        for ci in ("in_flight", "unregistered"):
            with self.subTest(ci=ci):
                source = Source(snapshot(currency="update_candidate", ci=ci))
                self.actor.reconcile(self.key, source)
                self.assertEqual(source.updates, [])

    def test_reread_before_and_after_server_update_discards_old_head(self):
        self.activate()
        old = snapshot(currency="update_candidate")
        new = snapshot(head="c" * 40, ci="unregistered")
        source = Source(old, old, new)
        result = self.actor.reconcile(self.key, source)
        self.assertEqual(source.reads, 3)
        self.assertEqual(source.updates, [old["head"]])
        self.assertEqual(json.loads(result["observed"])["head"], new["head"])
        self.assertEqual(json.loads(result["delivery"]["payload"])["observed"]["ci"], "unregistered")

    def test_new_workflow_or_head_at_prewrite_reread_prevents_update(self):
        self.activate()
        for latest in (snapshot(ci="in_flight", currency="update_candidate"),
                       snapshot(head="d" * 40, currency="current"), snapshot(currency="conflict")):
            with self.subTest(latest=latest):
                source = Source(snapshot(currency="update_candidate"), latest)
                self.actor.db.execute("UPDATE authorities SET update_head=NULL,update_started=NULL")
                self.actor.reconcile(self.key, source)
                self.assertEqual(source.updates, [])

    def test_accepted_asynchronous_update_is_not_submitted_twice(self):
        self.activate()
        old = snapshot(currency="update_candidate")
        source = Source(old)
        self.actor.reconcile(self.key, source)
        self.now = 120
        self.actor.reconcile(self.key, source)
        self.assertEqual(source.updates, [old["head"]])
        self.now = 241
        result = self.actor.reconcile(self.key, source)
        self.assertIn("has not settled", result["degraded"])
        self.assertEqual(source.updates, [old["head"]])

    def test_unchanged_observations_and_duplicate_hints_never_replay_received_work(self):
        self.activate()
        source = Source()
        self.actor.reconcile(self.key, source)
        delivery = self.admit()
        result = self.actor.acknowledge(self.key, delivery["generation"], delivery["fence"], "delivery-token", source)
        self.assertTrue(result["acknowledged"])
        for _ in range(20):
            self.actor.hint(self.key)
        self.now = 120
        result = self.actor.reconcile(self.key, source)
        self.assertEqual(result["generation"], delivery["generation"])
        self.assertEqual(result["delivery"]["status"], "received")
        self.assertEqual(source.reads, 3)

    def test_hint_deadline_is_separate_and_real_periodic_outage_is_retained(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        self.now = 10
        self.actor.hint(self.key)
        self.assertEqual(self.actor.status(self.key)["next_due"], 120)
        self.assertEqual(self.actor.due(), [self.key])
        self.actor.reconcile(self.key, Source())
        self.assertEqual(self.actor.due(), [])
        self.now = 131
        record = self.actor.reconcile(self.key, Source())
        self.assertIn("supervision_gap", json.loads(record["proposal"])["reasons"])
        self.assertEqual(record["gap_start"], 130)

    def test_rollback_then_retransfer_reactivates_fenced_delivery(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        stale = self.admit()
        with patch.object(self.actor, "source", return_value=Source()):
            self.actor.rollback(self.key, lambda *_args: None)
            self.actor.transfer(self.key, ["keep-current-7"], [], lambda *_args: None)
        self.actor.reconcile(self.key, Source())
        renewed = self.actor.inbox.get(self.key)
        self.assertEqual(renewed["status"], "pending")
        self.assertGreater(renewed["fence"], stale["fence"])
        self.assertFalse(self.actor.acknowledge(self.key, stale["generation"], stale["fence"],
                                              stale["admission"], Source())["acknowledged"])

    def test_acknowledgment_performs_a_fresh_read_and_persists_evidence(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        delivery = self.admit()
        source = Source()
        result = self.actor.acknowledge(self.key, delivery["generation"], delivery["fence"], "delivery-token", source)
        self.assertEqual(source.reads, 1)
        self.assertTrue(result["acknowledged"])
        self.assertEqual(self.actor.status(self.key)["authority"]["acknowledged"], delivery["generation"])
        self.assertEqual(json.loads(self.actor.status(self.key)["authority"]["ack_evidence"])["head"], result["head"])

    def test_changed_head_or_failed_read_cannot_acknowledge_old_work(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        delivery = self.admit()
        changed = self.actor.acknowledge(self.key, delivery["generation"], delivery["fence"], "delivery-token",
                                         Source(snapshot(head="c" * 40)))
        self.assertFalse(changed["acknowledged"])
        with self.assertRaises(ACTIVE.SHADOW.ObservationError):
            self.actor.acknowledge(self.key, delivery["generation"], delivery["fence"], "delivery-token",
                                   Source(ACTIVE.SHADOW.ObservationError("credentials unavailable")))
        self.assertEqual(self.actor.inbox.get(self.key)["status"], "admitted")

    def test_stop_atomically_fences_delivery_and_all_future_actions(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        delivery = self.admit()
        self.actor.control(self.key, "stop", "explicit user stop")
        self.assertEqual(self.actor.inbox.get(self.key)["status"], "stopped")
        self.assertIsNone(self.actor.inbox.get(self.key)["admission"])
        source = Source(snapshot(currency="update_candidate"))
        self.actor.reconcile(self.key, source)
        self.assertEqual(source.reads, 0)
        self.assertFalse(self.actor.acknowledge(self.key, delivery["generation"], delivery["fence"], "delivery-token", source)["acknowledged"])
        self.assertEqual(source.updates, [])

    def test_terminal_cleanup_is_atomic_with_observation(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        result = self.actor.reconcile(self.key, Source(snapshot(state="MERGED")))
        self.assertEqual(result["stopped"], "merged")
        self.assertEqual(result["delivery"]["status"], "stopped")
        self.assertEqual(self.actor.ledger.due(1000), [])

    def test_hold_survives_restart_and_explicit_release_keeps_same_actor(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        self.actor.control(self.key, "hold", "owner hold")
        other = ACTIVE.ActiveSupervisor(self.path, clock=lambda: 120)
        try:
            self.assertEqual(other.status(self.key)["held"], "owner hold")
            self.assertEqual(other.inbox.get(self.key)["held"], "owner hold")
            other.control(self.key, "release", "explicit release")
            self.assertEqual(other.status(self.key)["authority"]["state"], "active")
            self.assertIsNone(other.inbox.get(self.key)["held"])
        finally:
            other.close()

    def test_conflict_resolution_resumes_same_authority(self):
        self.activate()
        result = self.actor.reconcile(self.key, Source(snapshot(currency="conflict")))
        self.assertEqual(json.loads(result["delivery"]["payload"])["proposal"]["next_action"], "resolve_conflict")
        resolved = self.actor.reconcile(self.key, Source(snapshot(head="c" * 40)))
        self.assertEqual(resolved["authority"]["state"], "active")
        self.assertIn("conflict_resolved", json.loads(resolved["delivery"]["payload"])["proposal"]["reasons"])

    def test_transfer_stops_old_actor_before_new_authority_is_active(self):
        sequence = []
        def control(operation, service, context):
            sequence.append((operation, service, self.actor.status(self.key)["authority"]["state"]))
        with patch.object(self.actor, "source", return_value=Source()):
            result = self.actor.transfer(self.key, ["old-currency", "old-ci"], [{"id": "old-timer"}], control)
        self.assertEqual(sequence, [("stop", "old-currency", "transferring"), ("stop", "old-ci", "transferring")])
        self.assertEqual(result["authority"]["state"], "active")

    def test_failed_transfer_never_enables_new_writer(self):
        def fail(*_args):
            raise RuntimeError("old service stop unavailable")
        with self.assertRaises(RuntimeError):
            self.actor.transfer(self.key, ["old-service"], [], fail)
        self.assertEqual(self.actor.status(self.key)["authority"]["state"], "transferring")
        source = Source(snapshot(currency="update_candidate"))
        self.actor.reconcile(self.key, source)
        self.assertEqual(source.updates, [])
        self.assertIsNone(self.actor.status(self.key)["delivery"])

    def test_rollback_fences_delivery_before_restoring_old_route(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        operations = []
        def restore(operation, service, _context):
            operations.append((operation, service, self.actor.inbox.get(self.key)["status"],
                               self.actor.status(self.key)["authority"]["state"]))
        with patch.object(self.actor, "source", return_value=Source()):
            result = self.actor.rollback(self.key, restore)
        self.assertEqual(operations, [("restart", "keep-current-7", "stopped", "rollback")])
        self.assertTrue(result["restored"])
        self.assertIn("cannot cold-resume", result["limitation"])
        self.assertEqual(self.actor.status(self.key)["authority"]["state"], "shadow")

    def test_rollback_never_clears_a_stop_or_hold(self):
        for operation in ("stop", "hold"):
            with self.subTest(operation=operation):
                # One retained record is enough: stop is intentionally permanent.
                if operation == "stop":
                    self.actor.control(self.key, "stop", "owner stop")
                else:
                    self.actor.control(self.key, "hold", "owner hold")
                with patch.object(self.actor, "source", side_effect=AssertionError("must not read")):
                    result = self.actor.rollback(self.key, lambda *_args: self.fail("must not restart"))
                self.assertFalse(result["restored"])

    def test_concurrent_registration_retains_one_authoritative_owner(self):
        def register(index):
            actor = ACTIVE.ActiveSupervisor(self.path)
            try:
                return actor.register("github.com", "example/project", 7, f"author-{index}",
                                      {**self.context, "session": f"other-{index}"})
            finally:
                actor.close()
        with ThreadPoolExecutor(max_workers=8) as workers:
            records = list(workers.map(register, range(8)))
        self.assertTrue(all(json.loads(record["context"])["session"] == "owner" for record in records))
        self.assertEqual(self.actor.db.execute("SELECT count(*) FROM authorities").fetchone()[0], 1)

    def test_stop_drains_remote_mutation_without_locking_heartbeats(self):
        self.activate()
        entered, stop_requested, stopped = threading.Event(), threading.Event(), threading.Event()
        def stop():
            other = ACTIVE.ActiveSupervisor(self.path, clock=lambda: 0)
            try:
                stop_requested.set()
                other.control(self.key, "stop", "stop before push")
                stopped.set()
            finally:
                other.close()
        source = Source(snapshot(currency="update_candidate"), snapshot(currency="update_candidate"),
                        snapshot(head="c" * 40, ci="unregistered"))
        def update(head):
            source.updates.append(head)
            entered.set()
            worker.start()
            self.assertTrue(stop_requested.wait(5))
            heartbeat = ACTIVE.ActiveSupervisor(self.path, clock=lambda: 0)
            try:
                heartbeat.db.execute("PRAGMA busy_timeout=0")
                heartbeat.db.execute("UPDATE owners SET heartbeat=1")
                self.assertFalse(stopped.is_set())
            finally:
                heartbeat.close()
        worker = threading.Thread(target=stop)
        source.update = update
        self.actor.reconcile(self.key, source)
        worker.join(5)
        self.assertTrue(entered.is_set())
        self.assertTrue(stopped.is_set())
        later = Source(snapshot(currency="update_candidate"))
        self.actor.reconcile(self.key, later)
        self.assertEqual(later.reads, 0)
        self.assertEqual(self.actor.inbox.get(self.key)["status"], "stopped")

    def test_update_client_uses_only_expected_head_server_merge(self):
        source = ACTIVE.GitHub("github.com", "example/project", 7, "author")
        with patch.object(ACTIVE.subprocess, "run") as run:
            source.update("a" * 40)
        command = run.call_args.args[0]
        self.assertEqual(command[command.index("--method") + 1], "PUT")
        self.assertIn("/repos/example/project/pulls/7/update-branch", command)
        self.assertIn("expected_head_sha=" + "a" * 40, command)
        self.assertNotIn("--rebase", command)
        self.assertNotIn("merge", command)

    def test_live_rpc_work_does_not_block_reconciliation_or_launch_twice(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        self.actor.db.execute("""INSERT INTO owners
            (session,file,cwd,provider,model,effort,process,heartbeat,authentication)
            VALUES ('owner','fixture.jsonl',?,'fixture','model','high','old-process',-20,'config')""", (self.temporary.name,))
        started, release = threading.Event(), threading.Event()
        def activate(inbox, _owner, _omp):
            started.set()
            self.assertTrue(release.wait(5))
            inbox.db.execute("UPDATE deliveries SET status='received'")
            return "received"
        pool = ACTIVE.DeliveryHost(self.actor)
        try:
            with patch.object(ACTIVE.HOST, "activate", side_effect=activate) as launch:
                pool.poll()
                self.assertTrue(started.wait(5))
                self.assertEqual(pool.poll(), [])
                self.actor.reconcile(self.key, Source())
                self.assertEqual(len(pool.running), 1)
                self.assertEqual(launch.call_count, 1)
                release.set()
                pool.close()
                self.assertEqual(pool.poll(), [{"session":"owner","outcome":"received"}])
        finally:
            release.set()
            pool.close()

    def test_service_control_rejects_another_owner_before_any_stop(self):
        import subprocess
        metadata = {"owner":"another-owner","cwd":self.temporary.name,"key":"old-service",
                    "proc":{"env":{"fixture-only":"DO_NOT_FORWARD"}}}
        with patch.object(ACTIVE.subprocess, "run", return_value=subprocess.CompletedProcess([],0,json.dumps(metadata),"")) as run:
            with self.assertRaisesRegex(ValueError, "not owned"):
                SERVICE_CONTROL("stop", "old-service", self.context)
        self.assertEqual(run.call_count, 1)

    def test_stale_ack_after_a_new_head_does_not_even_read_github(self):
        self.activate()
        self.actor.reconcile(self.key, Source())
        stale = self.admit()
        self.actor.reconcile(self.key, Source(snapshot(head="c" * 40)))
        fresh = Source()
        result = self.actor.acknowledge(self.key, stale["generation"], stale["fence"], "delivery-token", fresh)
        self.assertFalse(result["acknowledged"])
        self.assertEqual(fresh.reads, 0)

    def test_shadow_only_controls_refuse_without_remote_work(self):
        self.actor.db.execute("DELETE FROM authorities WHERE identity=?", (self.key,))
        with patch.object(self.actor,"source",side_effect=AssertionError("must not read")), \
                patch.object(self.actor,"host_running",side_effect=AssertionError("must not probe")):
            self.assertFalse(self.actor.acknowledge(self.key,1,1,"missing")["acknowledged"])
            self.assertIn("refused",self.actor.transfer(self.key,[],[]))
            self.assertFalse(self.actor.rollback(self.key)["restored"])

    def test_shadow_only_cli_requests_return_structured_refusals(self):
        self.actor.db.execute("DELETE FROM authorities WHERE identity=?", (self.key,))
        before = self.actor.ledger.get(self.key)
        prefix = [sys.executable,str(ROOT / "scripts/pr-active-supervisor.py"),"--database",str(self.path)]
        for key in (self.key,"isolated.example/missing/project/999"):
            result = subprocess.run(prefix+["acknowledge",key,"--generation","1","--fence","1","--admission","missing"],
                                    capture_output=True,text=True,check=True)
            self.assertFalse(json.loads(result.stdout)["acknowledged"])
            self.assertEqual(result.stderr,"")
            result = subprocess.run(prefix+["transfer",key,"--request","-"],
                                    input=json.dumps({"services":[],"cancelled_timers":[]}),
                                    capture_output=True,text=True,check=True)
            self.assertIn("refused",json.loads(result.stdout))
            self.assertEqual(result.stderr,"")
        self.assertEqual(self.actor.ledger.get(self.key),before)

    def test_identical_trace_compares_wakes_reconciliation_and_action_latency(self):
        self.activate()
        # The baseline is explicitly the former configured 120-second owner
        # reminder plus currency poll, not invented production fleet telemetry.
        transitions = [(0,snapshot(ci="in_flight")),(121,snapshot()),
                       (251,snapshot(feedback=[["comments",1]])),(480,snapshot(state="MERGED"))]
        def evidence(now):
            return next(value for at,value in reversed(transitions) if at<=now)
        active = {"reconciliations":0,"agent_wakes":0,"event_to_action_seconds":[]}
        baseline = {"reconciliations":0,"agent_wakes":0,"event_to_action_seconds":[]}
        active_actions, baseline_actions = {}, {}
        for now in range(601):
            self.now = now
            if now in (10,122,252,481):
                for _ in range(20):
                    self.actor.hint(self.key)
            if self.key in self.actor.due():
                active["reconciliations"] += 1
                source = Source(evidence(now))
                record = self.actor.reconcile(self.key,source)
                if record["delivery"] and record["delivery"]["status"] == "pending":
                    active["agent_wakes"] += 1
                    delivery = self.admit()
                    self.assertTrue(self.actor.acknowledge(self.key,delivery["generation"],
                        delivery["fence"],"delivery-token",source)["acknowledged"])
                    for event in (121,251):
                        if now>=event:
                            active_actions.setdefault(event,now)
            if now%120 == 0 and now<=480:
                baseline["reconciliations"] += 1
                baseline["agent_wakes"] += 1
                for event in (121,251):
                    if now>=event:
                        baseline_actions.setdefault(event,now)
        active["event_to_action_seconds"] = [active_actions[event]-event for event in (121,251)]
        baseline["event_to_action_seconds"] = [baseline_actions[event]-event for event in (121,251)]
        self.assertEqual(active,{"reconciliations":7,"agent_wakes":3,"event_to_action_seconds":[1,1]})
        self.assertEqual(baseline,{"reconciliations":5,"agent_wakes":5,"event_to_action_seconds":[119,109]})
        print("Identical fixture trace (configured legacy timer model): " +
              json.dumps({"active":active,"legacy":baseline},sort_keys=True))

    def test_queued_legacy_wake_is_fenced_and_running_work_must_drain(self):
        wake = self.actor.legacy_wake(self.key,"admit",context={"message":"Read current PR state","delaySeconds":120})
        self.assertTrue(wake["authorized"])
        self.activate()
        self.assertFalse(self.actor.legacy_wake(self.key,"start",wake["token"],wake["epoch"])["authorized"])
        with patch.object(self.actor,"source",return_value=Source()):
            self.actor.rollback(self.key,lambda *_args:None)
        wake = self.actor.legacy_wake(self.key,"admit",context={"message":"Read current PR state","delaySeconds":120})
        self.assertTrue(self.actor.legacy_wake(self.key,"start",wake["token"],wake["epoch"])["authorized"])
        with self.assertRaisesRegex(ValueError,"drain"):
            self.activate()
        self.actor.legacy_wake(self.key,"finish",wake["token"],wake["epoch"])
        self.activate()
        self.assertFalse(self.actor.legacy_wake(self.key,"check",wake["token"],wake["epoch"])["authorized"])

    def test_lost_legacy_admission_recovers_after_restart_and_fences_old_tokens(self):
        context = {"message":"Retain the original owner continuation","delaySeconds":120}
        lost = self.actor.legacy_wake(self.key,"admit",context=context)
        self.now = 60
        restarted = ACTIVE.ActiveSupervisor(self.path,clock=lambda:self.now)
        try:
            recovered = restarted.recover_legacy("owner")
            self.assertEqual(len(recovered),1)
            self.assertEqual(recovered[0]["context"],context)
            self.assertEqual(restarted.recover_legacy("another-owner"),[])
            early = restarted.legacy_wake(self.key,"retry",lost["token"],lost["epoch"])
            self.assertFalse(early["authorized"])
            self.assertTrue(early["pending"])
            self.now = 120
            renewed = restarted.legacy_wake(self.key,"retry",lost["token"],lost["epoch"])
            self.assertTrue(renewed["authorized"])
            self.assertNotEqual(renewed["token"],lost["token"])
            self.assertEqual(renewed["context"],context)
            self.assertFalse(restarted.legacy_wake(self.key,"start",lost["token"],lost["epoch"])["authorized"])
            restarted.legacy_wake(self.key,"finish",lost["token"],lost["epoch"])
            self.assertTrue(restarted.legacy_wake(self.key,"start",renewed["token"],renewed["epoch"])["authorized"])
            # A queued lease can expire. A running owner cannot be reclaimed
            # merely because its timestamp is old or this process restarted.
            self.now = 10000
            self.assertFalse(restarted.legacy_wake(self.key,"retry",renewed["token"],renewed["epoch"])["authorized"])
            self.assertFalse(restarted.legacy_wake(self.key,"admit",context=context)["authorized"])
            self.assertEqual(restarted.recover_legacy("owner"),[])
            self.assertTrue(restarted.legacy_wake(self.key,"check",renewed["token"],renewed["epoch"])["authorized"])
            restarted.control(self.key,"stop","explicit owner stop")
            self.assertFalse(restarted.legacy_wake(self.key,"check",renewed["token"],renewed["epoch"])["authorized"])
        finally:
            restarted.close()

    def test_legacy_retry_budget_and_hold_transfer_fences_survive_restart(self):
        context = {"message":"Read current PR state","delaySeconds":120}
        wake = self.actor.legacy_wake(self.key,"admit",context=context)
        for attempt in range(2,6):
            self.now += 120
            wake = self.actor.legacy_wake(self.key,"retry",wake["token"],wake["epoch"])
            self.assertTrue(wake["authorized"])
        self.now += 120
        self.assertFalse(self.actor.legacy_wake(self.key,"retry",wake["token"],wake["epoch"])["authorized"])
        self.assertEqual(self.actor.status(self.key)["authority"]["legacy_attempts"],5)
        self.assertIn("retry limit",self.actor.status(self.key)["authority"]["error"])
        self.actor.control(self.key,"hold","explicit hold")
        self.assertEqual(self.actor.recover_legacy("owner"),[])
        self.actor.control(self.key,"release","explicit release")
        fresh = self.actor.legacy_wake(self.key,"admit",context=context)
        self.assertTrue(fresh["authorized"])
        self.assertFalse(self.actor.legacy_wake(self.key,"start",wake["token"],wake["epoch"])["authorized"])
        self.activate()
        self.assertFalse(self.actor.legacy_wake(self.key,"retry",fresh["token"],fresh["epoch"])["authorized"])
        self.assertEqual(self.actor.recover_legacy("owner"),[])


if __name__ == "__main__":
    unittest.main()
