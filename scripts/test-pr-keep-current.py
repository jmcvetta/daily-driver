#!/usr/bin/env python3
"""Exercise the real keep-current loop against a stateful offline `gh` client."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "pr-keep-current.sh"
FAKE_GH = '''#!/usr/bin/env python3
import json
import os
import sys

state_path = os.environ["FAKE_GH_STATE"]
log_path = os.environ["FAKE_GH_LOG"]
args = sys.argv[1:]
def load():
    with open(state_path, encoding="utf-8") as source:
        return json.load(source)
def save(state):
    temporary = state_path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as target:
        json.dump(state, target)
    os.replace(temporary, state_path)
def log(value):
    with open(log_path, "a", encoding="utf-8") as target:
        target.write(value + "\\n")

if args[:2] == ["pr", "view"]:
    log("view:url")
    print("https://github.com/example/project/pull/25")
elif args[:3] == ["api", "--hostname", "github.com"]:
    state = load()
    endpoint = args[-1]
    if "--method" in args and args[args.index("--method") + 1] == "PUT":
        state["updates"] += 1
        log("update")
        if state["conflict_update"]:
            save(state)
            print("Cannot update PR branch due to conflicts", file=sys.stderr)
            raise SystemExit(1)
        if state["fail_update"]:
            save(state)
            print("fixture update failed", file=sys.stderr)
            raise SystemExit(1)
        state["stale"] = False
        state["head"] = "c" * 40
        save(state)
        print("fixture update accepted")
    elif "/compare/" in endpoint:
        log("compare")
        if state.get("deny_compare"):
            raise SystemExit(1)
        print(json.dumps({"merge_base_commit": {"sha": "d" * 40 if state["stale"] else state["base"]},
                          "behind_by": 1 if state["stale"] else 0}))
    elif endpoint.endswith("/pulls/25"):
        log("pull")
        print(json.dumps({"state": "closed" if state["state"] != "OPEN" else "open",
                          "merged": state["state"] == "MERGED", "head": {"sha": state["head"]},
                          "base": {"ref": "release", "sha": state["base"]},
                          "mergeable": state["merge_state"] != "DIRTY",
                          "mergeable_state": state["merge_state"].lower()}))
    else:
        raise SystemExit("unexpected endpoint: " + endpoint)
else:
    raise SystemExit("unsupported gh command: " + " ".join(args))
'''


class KeepCurrentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="keep-current-test-")
        self.root = Path(self.temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state_path = self.root / "state.json"
        self.log_path = self.root / "gh.log"
        self.output_path = self.root / "watch.log"
        fake = self.bin / "gh"
        fake.write_text(FAKE_GH, encoding="utf-8")
        fake.chmod(0o755)
        self.process = None
        self.output = None

    def tearDown(self):
        self.stop_watch()
        self.temporary.cleanup()

    def start_watch(self, **overrides):
        state = {
            "state": "OPEN",
            "merge_state": "BEHIND",
            "run_in_flight": False,
            "stale": True,
            "head": "a" * 40,
            "base": "b" * 40,
            "fail_update": False,
            "conflict_update": False,
            "updates": 0,
            **overrides,
        }
        self.write_state(state)
        environment = os.environ.copy()
        environment.update({
            "PATH": f"{self.bin}{os.pathsep}{environment['PATH']}",
            "FAKE_GH_STATE": str(self.state_path),
            "FAKE_GH_LOG": str(self.log_path),
            "KEEP_CURRENT_INTERVAL": "0.05",
        })
        self.output = self.output_path.open("w+", encoding="utf-8")
        self.process = subprocess.Popen(
            ["bash", str(SCRIPT), "25"],
            cwd=self.root,
            env=environment,
            stdout=self.output,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def write_state(self, state):
        temporary = self.state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        temporary.replace(self.state_path)

    def read_state(self):
        return json.loads(self.state_path.read_text(encoding="utf-8"))

    def read_log(self, path):
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def wait_for(self, condition, description, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            if self.process is not None and self.process.poll() is not None:
                self.fail(f"watch exited before {description}: {self.read_log(self.output_path)}")
            time.sleep(0.02)
        self.fail(f"timed out waiting for {description}: {self.read_log(self.output_path)}")

    def stop_watch(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=2)
        if self.output is not None:
            self.output.close()
            self.output = None

    def test_behind_branch_updates_during_in_flight_ci(self):
        """A behind branch advances without waiting for its current CI run."""
        self.start_watch(run_in_flight=True)
        self.wait_for(lambda: self.read_state()["updates"] == 1, "the base update")
        state = self.read_state()
        self.assertTrue(state["run_in_flight"])
        self.assertFalse(state["stale"])
        self.assertEqual(1, self.read_log(self.log_path).splitlines().count("update"))
        self.assertNotIn("view:statusCheckRollup", self.read_log(self.log_path))

    def test_stale_masked_currency_updates_during_in_flight_ci(self):
        """A masked stale branch advances without waiting for CI."""
        for merge_state in ("DRAFT", "BLOCKED", "UNKNOWN"):
            with self.subTest(merge_state=merge_state):
                self.start_watch(merge_state=merge_state, run_in_flight=True)
                try:
                    self.wait_for(lambda: self.read_state()["updates"] == 1, "the masked base update")
                    state = self.read_state()
                    self.assertTrue(state["run_in_flight"])
                    self.assertFalse(state["stale"])
                    self.assertNotIn("view:statusCheckRollup", self.read_log(self.log_path))
                finally:
                    self.stop_watch()


    def test_current_branch_does_not_get_an_update(self):
        """Catch a watcher that performs unnecessary merges on a current branch."""
        self.start_watch(merge_state="UNKNOWN", stale=False, run_in_flight=True)
        self.wait_for(lambda: "compare" in self.read_log(self.log_path), "the first comparison")
        time.sleep(0.08)
        self.assertEqual(0, self.read_state()["updates"])

    def test_base_advance_after_handoff_triggers_update(self):
        """Catch a detached watch that checks currency only when it starts."""
        self.start_watch(merge_state="CLEAN", stale=False, run_in_flight=True)
        self.wait_for(lambda: "compare" in self.read_log(self.log_path), "the initial comparison")
        time.sleep(0.08)
        state = self.read_state()
        state["stale"] = True
        state["base"] = "e" * 40
        self.write_state(state)
        self.wait_for(lambda: self.read_state()["updates"] == 1, "the update after the base advances")

    def test_conflict_stops_without_an_update(self):
        """Catch a watcher that attempts an automated update across a conflict."""
        self.start_watch(merge_state="DIRTY")
        self.wait_for(lambda: self.process.poll() is not None, "the conflict stop")
        self.assertEqual(3, self.process.returncode)
        self.assertEqual(0, self.read_state()["updates"])

    def test_masked_conflict_stops_instead_of_retrying(self):
        """Catch a masked conflict that retries forever instead of alerting the owner."""
        self.start_watch(merge_state="DRAFT", conflict_update=True)
        self.wait_for(lambda: self.process.poll() is not None, "the masked conflict stop")
        self.assertEqual(3, self.process.returncode)
        self.assertEqual(1, self.read_state()["updates"])
        self.assertIn("conflicts with its base", self.read_log(self.output_path))

    def test_update_failure_is_reported_without_blind_retry(self):
        """An uncertain update result is not replayed against the same head."""
        self.start_watch(fail_update=True, run_in_flight=True)
        self.wait_for(lambda: "outcome uncertain" in self.read_log(self.output_path), "the failed update report")
        time.sleep(0.4)
        self.assertEqual(self.read_state()["updates"], 1)

    def test_denied_comparison_never_updates(self):
        """Denied ancestry cannot authorize a speculative update."""
        self.start_watch(deny_compare=True, run_in_flight=True)
        self.wait_for(lambda: "read failed" in self.read_log(self.output_path), "the comparison failure")
        self.assertEqual(self.read_state()["updates"], 0)

    def test_merged_and_closed_prs_stop(self):
        """Catch a watcher that keeps polling a PR after it has ended."""
        for state in ("MERGED", "CLOSED"):
            with self.subTest(state=state):
                self.start_watch(state=state)
                self.wait_for(lambda: self.process.poll() is not None, f"the {state} stop")
                self.assertEqual(0, self.process.returncode)
                self.assertEqual(0, self.read_state()["updates"])
                self.stop_watch()


if __name__ == "__main__":
    unittest.main()
