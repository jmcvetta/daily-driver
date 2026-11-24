#!/usr/bin/env python3
"""Exercise active fresh-read ACK, host restart and queued-stop without a real PR.

The child-resumption probe seeds real isolated owner sessions and calls run().
Only its disposable local fixture and transient systemd user unit are used.
"""
from __future__ import annotations

import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("active_probe_product", ROOT / "scripts/pr-active-supervisor.py")
ACTIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ACTIVE)
IDENTITY = "isolated.example/fixture/active/8"


def worker(base):
    """Resume actual child work under a restarting, bounded service manager."""
    phase = json.loads((base / "active-phase.json").read_text())
    actor = ACTIVE.ActiveSupervisor(base / "active.sqlite")
    try:
        with open(str(actor.ledger.path) + ".actor-lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if phase["starts"] == 0:
                actor.transfer(IDENTITY, [], [])
            result = actor.reconcile(IDENTITY)
            assert not result["degraded"], result["degraded"]
            owner = dict(actor.db.execute("SELECT * FROM owners WHERE session=?", (phase["session"],)).fetchone())
            outcome = ACTIVE.HOST.activate(actor.inbox, owner, shutil.which("omp"), timeout=40)
            assert outcome == "received", outcome
            acknowledged = actor.status(IDENTITY)["authority"]
            evidence = json.loads(acknowledged["ack_evidence"])
            assert acknowledged["acknowledged"] == phase["starts"] + 1, acknowledged["acknowledged"]
            assert evidence["head"] == ("a" if phase["starts"] == 0 else "b") * 40
            if phase["starts"] == 0:
                (base / "active-head.json").write_text(json.dumps({"head":"b" * 40}))
                actor.hint(IDENTITY)
                (base / "active-phase.json").write_text(json.dumps({**phase,"starts":1}))
                return 75  # The service manager, not this worker, restarts it.
            # Stop while the cold parent's turn is queued/in flight, before its
            # native child write. The dispatch guard must reject that stale
            # wake without making a child provider request or acknowledging it.
            (base / "active-head.json").write_text(json.dumps({"head":"c" * 40}))
            result = actor.reconcile(IDENTITY)
            assert result["generation"] == 3, result["generation"]
            (base / "stop-before-child-dispatch").touch()
            outcome = ACTIVE.HOST.activate(actor.inbox, owner, shutil.which("omp"), timeout=40)
            assert outcome == "stopped-or-idle", outcome
            result = actor.status(IDENTITY)
            assert result["stopped"] == "isolated queued stop"
            assert result["delivery"]["status"] == "stopped"
            assert result["authority"]["acknowledged"] == 2
            assert actor.due() == []
            (base / "active-result.json").write_text(json.dumps({
                "active_host_starts":2,"fresh_work_acknowledgments":[1,2],
                "acknowledged_heads":["a" * 40,"b" * 40],"queued_stopped_generation":3,
                "task_context_retained":json.loads(result["context"])["session"] == phase["session"]}))
            return 0
    finally:
        actor.close()


def run(base, env, inbox, owner):
    """Run only against the disposable sessions seeded by the child proof."""
    primary = base / "active-repository"
    task = base / "active-task"
    subprocess.run(["git", "init", "--initial-branch=master", str(primary)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(primary), "-c", "user.name=Fixture", "-c",
                    "user.email=fixture@example.invalid", "commit", "--allow-empty", "-m", "Fixture"],
                   check=True, capture_output=True)
    subprocess.run(["git", "-C", str(primary), "worktree", "add", "-b", "isolated-proof", str(task)],
                   check=True, capture_output=True)
    actor = ACTIVE.ActiveSupervisor(base / "active.sqlite")
    try:
        columns = "session,file,cwd,provider,model,effort,process,heartbeat,authentication,agent"
        for row in inbox.db.execute("SELECT " + columns + " FROM owners"):
            actor.db.execute("INSERT INTO owners (" + columns + ") VALUES (?,?,?,?,?,?,?,?,?,?)", tuple(row))
        actor.register("isolated.example", "fixture/active", 8, "fixture-author", {
            "session":owner["session"],"worktree":str(task),"branch":"isolated-proof",
            "task":"isolated active lifecycle proof"})
    finally:
        actor.close()
    binary = base / "bin"
    binary.mkdir()
    fixture = binary / "gh"
    fixture.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
base = pathlib.Path(''' + repr(str(base)) + ''')
args = sys.argv[1:]
assert args[:5] == ["api","--hostname","isolated.example","--method","GET"] or args[:4] == ["api","--hostname","isolated.example","graphql"], "only isolated reads are allowed"
head = json.loads((base / "active-head.json").read_text())["head"]
with (base / "active-reads.jsonl").open("a") as log:
 log.write(json.dumps({"head":head}) + "\\n")
if "graphql" in args:
 print(json.dumps([{"data":{"repository":{"pullRequest":{"reviewThreads":{"nodes":[],"pageInfo":{"hasNextPage":False,"endCursor":None}}}}}}]))
else:
 endpoint = args[-1]
 assert endpoint.startswith("/repos/fixture/active/"), "wrong fixture identity"
 if endpoint.endswith("pulls/8"):
  print(json.dumps({"head":{"sha":head},"base":{"ref":"release","sha":"d"*40},"state":"open","merged":False,"mergeable":True,"mergeable_state":"clean"}))
 elif "/check-runs?" in endpoint:
  print(json.dumps([{"total_count":1,"check_runs":[{"id":1,"status":"completed","conclusion":"success"}]}]))
 elif "/actions/runs?" in endpoint:
  print(json.dumps([{"total_count":0,"workflow_runs":[]}]))
 else:
  assert any(part in endpoint for part in ("/statuses?","/comments?","/reviews?")), "unexpected fixture inventory"
  print("[[]]")
''')
    fixture.chmod(0o700)
    (base / "active-head.json").write_text(json.dumps({"head":"a" * 40}))
    (base / "active-phase.json").write_text(json.dumps({"session":owner["session"],"starts":0}))
    unit = "daily-driver-active-proof-" + uuid.uuid4().hex
    command = ["systemd-run","--user","--wait","--collect","--unit",unit,
        "--property=Restart=on-failure","--property=RestartSec=100ms",
        "--property=RuntimeMaxSec=100","--property=TimeoutStopSec=5",
        "--property=StartLimitBurst=2","--property=StartLimitIntervalSec=120",
        "--working-directory",str(base / "sandbox")]
    isolated = {**env,"PATH":str(binary) + os.pathsep + env["PATH"]}
    for key,value in isolated.items():
        command += ["--setenv",f"{key}={value}"]
    command += [sys.executable,str(Path(__file__).resolve()),"--worker",str(base)]
    try:
        result = subprocess.run(command,capture_output=True,text=True,timeout=120)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads((base / "active-result.json").read_text())
    finally:
        subprocess.run(["systemctl","--user","stop",unit],capture_output=True,timeout=15,check=False)


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        raise SystemExit("Run python3 scripts/probe-omp-child-resumption.py to seed isolated owner sessions")
    raise SystemExit(worker(Path(sys.argv[2])))
