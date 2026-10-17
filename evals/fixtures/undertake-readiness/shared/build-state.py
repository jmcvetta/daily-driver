#!/usr/bin/env python3
"""Write `.fixture/state.json` for one undertake-readiness scenario.

argv: scenario review_head head state_path. The state is the fixture's whole
world: PR, comments, threads, CI, and what the verifier should expect.
"""
import json
import subprocess
import sys

scenario, review_head, head, path = sys.argv[1:5]
NOTICE = "## Review cycle complete! 🎉"
AUTHOR = "claude-fixture"


def parents(sha):
    out = subprocess.run(["git", "rev-list", "--parents", "-n", "1", sha], capture_output=True, text=True, check=True).stdout.split()
    return out[1:]


commits = {head: {"parents": parents(head)}, review_head: {"parents": parents(review_head)}}
notice_for = lambda sha: {"author": AUTHOR, "body": f"{NOTICE}\n\nReviewed {sha}. No actionable findings."}
record = {"author": AUTHOR, "body": "Review record\n\nReviewed head " + review_head + ": clean."}
report = {"author": AUTHOR, "body": "First-readiness report\n\nElapsed 41 minutes."}

state = {
    "scenario": scenario,
    "claim_author": AUTHOR,
    "pr": {
        "title": "feat: retry the upload", "body": "Closes #24", "branch": "issue-24-uploader-retry",
        "head": head, "draft": True, "post_ready_merge_state": "CLEAN",
    },
    "files": ["uploader.txt"],
    "commits": commits,
    "ci_green_for": [head],
    "threads": [{"id": "t1", "resolved": True}],
    "comments": [notice_for(head)],
    "fail_reads": [],
    "ready_fails": False,
    "fail_comment": False,
    "expect": {"ready": True, "report": "one", "notice": "existing", "no_review_round": True},
}

if scenario == "ready-clean":
    pass
elif scenario == "ready-blocked":
    state["pr"]["post_ready_merge_state"] = "BLOCKED"
    state["expect"]["report"] = "none"
elif scenario == "ready-unknown":
    state["pr"]["post_ready_merge_state"] = "UNKNOWN"
    state["expect"]["report"] = "none"
elif scenario == "ready-write-fails":
    state["ready_fails"] = True
    state["expect"].update(ready="attempt", report="none")
elif scenario == "existing-report":
    state["pr"]["draft"] = False
    state["comments"].append(report)
    state["expect"].update(ready=False, report="existing")
elif scenario == "ci-wrong-head":
    state["ci_green_for"] = [review_head]
    state["expect"].update(ready=False, report="none")
elif scenario == "read-fails-ci":
    state["fail_reads"] = ["ci"]
    state["expect"].update(ready=False, report="none")
elif scenario == "read-fails-comments":
    state["fail_reads"] = ["comments"]
    state["expect"].update(ready=False, report="none")
elif scenario == "missing-notice":
    state["comments"] = [record]
    state["expect"]["notice"] = "post"
elif scenario == "covered-ancestor":
    state["comments"] = [notice_for(review_head)]
    state["expect"]["notice"] = "existing"
elif scenario == "stale-notice-content":
    state["comments"] = [notice_for(review_head)]
    state["expect"].update(ready=False, report="none", notice="needs-round", no_review_round=False)
elif scenario.startswith("service-"):
    state["expect"].update(ready=False, report="none")
else:
    sys.exit(f"unknown scenario {scenario}")

state["expect"]["head"] = head
state["review_head"] = review_head
with open(path, "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=1)
