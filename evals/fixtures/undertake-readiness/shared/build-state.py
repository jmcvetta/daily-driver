#!/usr/bin/env python3
"""Write `.fixture/state.json` for one undertake-readiness scenario.

argv: scenario review_head head state_path. The state is the fixture's whole
world: PR, comments, threads, CI, and what the verifier should expect.
"""
import json
import subprocess
import sys

scenario, review_head, head, path = sys.argv[1:5]
AUTHOR = "claude-fixture"


def parents(sha):
    out = subprocess.run(["git", "rev-list", "--parents", "-n", "1", sha], capture_output=True, text=True, check=True).stdout.split()
    return out[1:]


commits = {head: {"parents": parents(head)}, review_head: {"parents": parents(review_head)}}
review_for = lambda sha, author=AUTHOR: {"id": 101, "user": {"login": author}, "state": "COMMENTED", "commit_id": sha, "submitted_at": "2026-01-01T00:00:00Z", "body": "Full review: clean."}
verification = lambda scope, sha, outcome="clear", defects="none", wall="open", author=AUTHOR: {
    "author": author, "body": f"Review verification\nscope reviewed: {scope}\nverified: {sha}\noutcome: {outcome}\ndefects: {defects}\nwall: {wall}"}
report = {"author": AUTHOR, "body": "# First-readiness report 🎉\n\nElapsed 41 minutes."}

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
    "reviews": [review_for(head)],
    "comments": [],
    "behavior_changed": False,
    "fail_reads": [],
    "ready_fails": False,
    "fail_comment": False,
    "expect": {"ready": True, "report": "one", "no_review_round": True},
}

if scenario == "ready-clean":
    pass
elif scenario == "ready-blocked":
    state["pr"]["post_ready_merge_state"] = "BLOCKED"
elif scenario == "ready-unknown":
    state["pr"]["post_ready_merge_state"] = "UNKNOWN"
elif scenario == "ready-write-fails":
    state["ready_fails"] = True
    state["expect"].update(ready="attempt")
elif scenario == "report-write-fails":
    state["fail_comment"] = True
    state["expect"].update(ready="none", report="failed")
elif scenario == "existing-report":
    state["comments"].append(report)
    state["expect"].update(ready=True, report="existing")
elif scenario == "ci-wrong-head":
    state["ci_green_for"] = [review_head]
    state["expect"].update(ready=False, report="none")
elif scenario == "read-fails-ci":
    state["fail_reads"] = ["ci"]
    state["expect"].update(ready=False, report="none")
elif scenario == "read-fails-comments":
    state["fail_reads"] = ["comments"]
    state["expect"].update(ready=False, report="none")
elif scenario == "missing-review-record":
    state["reviews"] = []
    state["expect"].update(ready=False, report="none", no_review_round=False)
elif scenario in ("covered-ancestor", "rejected-only", "ancestry-unavailable"):
    state["reviews"] = [review_for(review_head)]
    if scenario == "rejected-only":
        state["reviews"][0]["body"] = "Full review: finding rejected; no behavioral fix implemented."
    if scenario == "ancestry-unavailable":
        state["fail_reads"] = ["commits"]
        state["expect"].update(ready=False, report="none", no_review_round=False)
elif scenario in ("stale-review-record", "verified-fix", "superseded-defective", "superseded-incomplete", "wrong-scope", "wrong-verification-author"):
    state["reviews"] = [review_for(review_head)]
    state["reviews"][0]["body"] = "Full review: finding identified; behavioral fix implemented after review."
    state["behavior_changed"] = True
    if scenario != "stale-review-record":
        state["comments"] = [verification(review_head, head)]
    if scenario == "superseded-defective":
        state["comments"].append(verification(review_head, head, "defects", "present"))
    elif scenario == "superseded-incomplete":
        state["comments"].append(verification(review_head, head, "incomplete"))
    elif scenario == "wrong-scope":
        state["comments"] = [verification(head, head)]
    elif scenario == "wrong-verification-author":
        state["comments"] = [verification(review_head, head, author="other-reviewer")]
    if scenario != "verified-fix":
        state["expect"].update(ready=False, report="none", no_review_round=False)
elif scenario == "wrong-review-author":
    state["reviews"] = [review_for(head, "other-reviewer")]
    state["expect"].update(ready=False, report="none", no_review_round=False)
elif scenario == "currency-stale":
    state["reviews"] = []
    state["expect"].update(ready=False, report="none", no_review_round=True)
elif scenario.startswith("service-"):
    state["pr"]["draft"] = False
    state["expect"].update(ready=False, report="none")
else:
    sys.exit(f"unknown scenario {scenario}")

state["expect"]["head"] = head
state["review_head"] = review_head
with open(path, "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=1)
