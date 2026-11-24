#!/usr/bin/env python3
"""Write `.fixture/state.json` for one undertake-readiness scenario.

argv: scenario review_head head state_path. Review independence, content
comparison and follow-up outcomes are declared simulation inputs, not proof
that this fixture performed a review. GitHub records supply readable context.
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
review_for = lambda sha, author="independent-reviewer": {
    "id": 101, "user": {"login": author}, "state": "APPROVED", "commit_id": sha,
    "submitted_at": "2026-01-01T00:00:00Z",
    "body": "Independent human review of the uploader retry: complete, no remaining defects."}
verification = lambda scope, sha, author="independent-verifier": {
    "author": author,
    "body": f"Independent follow-up review of the uploader retry fix at {sha}. "
            f"The behavioral change since {scope} is covered; no remaining defects."}

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
    "review_evidence": {
        "available": True,
        "independent": True,
        "complete": True,
        "relevant_content_changed": False,
        "verification": None,
    },
    "fail_reads": [],
    "ready_fails": False,
    "expect": {"ready": True, "no_review_round": True},
}

if scenario == "ready-clean":
    pass
elif scenario == "report-delivery-fails":
    state["pr"]["draft"] = False
elif scenario == "ready-blocked":
    state["pr"]["post_ready_merge_state"] = "BLOCKED"
elif scenario == "ready-unknown":
    state["pr"]["post_ready_merge_state"] = "UNKNOWN"
elif scenario in ("ready-write-fails", "ready-write-fails-covered-ancestor"):
    state["ready_fails"] = True
    state["expect"].update(ready="attempt")
elif scenario == "ci-wrong-head":
    state["ci_green_for"] = [review_head]
    state["expect"].update(ready=False)
elif scenario == "read-fails-ci":
    state["fail_reads"] = ["ci"]
    state["expect"].update(ready=False)
elif scenario == "read-fails-comments":
    state["fail_reads"] = ["comments"]
    state["expect"].update(ready=False)
elif scenario == "missing-review-record":
    state["reviews"] = []
    state["review_evidence"]["available"] = False
    state["expect"].update(ready=False, no_review_round=False)
elif scenario in ("covered-ancestor", "ready-write-fails-covered-ancestor", "rejected-only", "ancestry-unavailable"):
    state["reviews"] = [review_for(review_head)]
    state["comments"] = [{
        "author": "independent-reviewer",
        "body": "Compared the reviewed content with the current PR: the base update "
                "only adds README.md; the uploader retry and its review scope are unchanged.",
    }]
    if scenario == "rejected-only":
        state["reviews"][0]["body"] = (
            "Independent review complete. A proposed finding was rejected after "
            "checking the retry behavior; no behavioral fix or remaining defect.")
    if scenario == "ancestry-unavailable":
        state["fail_reads"] = ["commits"]
elif scenario in ("stale-review-record", "verified-fix", "superseded-defective", "superseded-incomplete", "wrong-scope", "wrong-verification-author"):
    state["reviews"] = [review_for(review_head)]
    state["reviews"][0]["body"] = (
        "Independent review found a zero-length-body defect. A behavioral fix "
        "was implemented after this review and requires relevant independent review.")
    state["review_evidence"]["relevant_content_changed"] = True
    if scenario != "stale-review-record":
        state["comments"] = [verification(review_head, head)]
        state["review_evidence"]["verification"] = {
            "independent": True, "relevant": True, "complete": True, "defects": False,
        }
    if scenario == "superseded-defective":
        state["comments"].append({
            "author": "independent-verifier",
            "body": "The latest independent follow-up found an unresolved retry defect. "
                    "The earlier clean result no longer applies.",
        })
        state["review_evidence"]["verification"]["defects"] = True
    elif scenario == "superseded-incomplete":
        state["comments"].append({
            "author": "independent-verifier",
            "body": "The earlier clean result is withdrawn: independent review of "
                    "the zero-length-body behavior is not complete.",
        })
        state["review_evidence"]["verification"]["complete"] = False
    elif scenario == "wrong-scope":
        state["comments"] = [{
            "author": "independent-verifier",
            "body": "Independent follow-up reviewed README.md only. The uploader "
                    "retry fix has not received follow-up review.",
        }]
        state["review_evidence"]["verification"]["relevant"] = False
    elif scenario == "wrong-verification-author":
        state["comments"] = [verification(review_head, head, author="other-reviewer")]
    if scenario not in ("verified-fix", "wrong-verification-author"):
        state["expect"].update(ready=False, no_review_round=False)
elif scenario == "wrong-review-author":
    state["reviews"] = [review_for(head, "other-reviewer")]
elif scenario == "self-review":
    state["reviews"] = [review_for(head, AUTHOR)]
    state["reviews"][0]["body"] = (
        "Implementation author self-check only; no independent human or agent review.")
    state["review_evidence"]["independent"] = False
    state["expect"].update(ready=False, no_review_round=False)
elif scenario == "self-verification":
    state["reviews"] = [review_for(review_head)]
    state["reviews"][0]["body"] = (
        "Independent review found a zero-length-body defect. The behavioral fix "
        "implemented after this review still needs independent follow-up review.")
    state["review_evidence"]["relevant_content_changed"] = True
    state["review_evidence"]["verification"] = {
        "independent": False, "relevant": True, "complete": True, "defects": False,
    }
    state["comments"] = [{
        "author": AUTHOR,
        "body": "I implemented and self-checked the retry fix. No independent "
                "follow-up review has been performed.",
    }]
    state["expect"].update(ready=False, no_review_round=False)
elif scenario == "currency-stale":
    state["reviews"] = []
    state["review_evidence"]["available"] = False
    state["expect"].update(ready=False, no_review_round=True)
elif scenario.startswith("service-"):
    state["pr"]["draft"] = False
    state["expect"].update(ready=False)
else:
    sys.exit(f"unknown scenario {scenario}")

state["review_head"] = review_head
with open(path, "w", encoding="utf-8") as fh:
    json.dump(state, fh, indent=1)
