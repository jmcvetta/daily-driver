#!/usr/bin/env python3
"""`scripts/model-telemetry.py`'s comment parsers, checked against fixture
text rather than a live GitHub call -- credential-free, like the other
`check-*.py` legs.

WHAT IT ASSERTS

    The claim-comment provenance pair parses from both the pre-`provenance`-
    skill shape (`Model:`/`session:`, no `Harness:` line or leading `---`)
    and the current one (`provenance`'s block). A `First-readiness report`
    parses its provenance pair, head SHA, and elapsed minutes computed from
    its two ISO timestamps; a report whose `Elapsed:` line names no
    recoverable timestamps ("unavailable") reports `elapsed_minutes` as
    `None` rather than a guess. A `Review verification` comment parses its
    pass number, outcome, and finding count, and a comment recording
    `findings: none` counts zero rather than one finding literally named
    `none`. A pull request whose claim and readiness `Model:` lines disagree
    is flagged as a mismatch rather than silently trusting either one. A
    check-runs list with a name repeated by reruns counts each rerun once. A
    `## Model class` token reads back from a task issue's body, and a body
    naming none reads back `unlabelled`. A `Closes #N` line in a pull
    request's body reads back the issue number it names.

Loads `scripts/model-telemetry.py` the way `scripts/check-labels-fixtures.py`
loads `scripts/check-labels.py` -- `importlib`, because a hyphenated filename
is not an importable module name.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = Path(__file__).resolve().parent / "model-telemetry.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_module():
    spec = importlib.util.spec_from_file_location("model_telemetry", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def main() -> int:
    mt = load_module()
    errors: list[str] = []

    def check(label: str, condition: bool) -> None:
        if not condition:
            errors.append(label)

    # -- claim comment, both eras ------------------------------------------
    new_claim = read_fixture("model-telemetry-claim-new.txt")
    parsed = mt.parse_provenance_block(new_claim)
    check("new-shape claim: parses at all", parsed is not None)
    if parsed:
        check("new-shape claim: model", parsed["model"] == "claude-sonnet-5")
        check("new-shape claim: harness", parsed["harness"] == "Claude Code 2.1.283")
        check(
            "new-shape claim: session",
            parsed["session"] == "https://claude.ai/code/session_01UgrMjQF4eeFhbXcHPDnVoK",
        )

    old_claim = read_fixture("model-telemetry-claim-old.txt")
    parsed_old = mt.parse_provenance_block(old_claim)
    check("old-shape claim: parses at all", parsed_old is not None)
    if parsed_old:
        check("old-shape claim: model", parsed_old["model"] == "claude-sonnet-5")
        check("old-shape claim: no Harness line means harness is None", parsed_old["harness"] is None)
        check(
            "old-shape claim: session",
            parsed_old["session"] == "https://claude.ai/code/session_01AS1Zx5kX3RvmomRuApS4Av",
        )

    found = mt.find_claim_comment(
        [
            {"body": "unrelated comment with no Branch: line", "created_at": "2026-09-28T12:00:00Z"},
            {"body": new_claim, "created_at": "2026-09-28T12:35:20Z"},
        ]
    )
    check("find_claim_comment: picks the comment carrying Branch: and a provenance pair", found is not None)

    # -- readiness report ----------------------------------------------------
    good_report = read_fixture("model-telemetry-readiness-good.txt")
    readiness = mt.parse_readiness_report(good_report)
    check("readiness: model", readiness["model"] == "claude-sonnet-5")
    check("readiness: harness", readiness["harness"] == "Claude Code 2.1.283")
    check("readiness: head sha", readiness["head_sha"] == "9786d61ef31146ef00faeb3e78120810db9bc677")
    check("readiness: claimed_at", readiness["claimed_at"] == "2026-09-28T12:35:20Z")
    check("readiness: ready_at", readiness["ready_at"] == "2026-09-28T13:07:04Z")
    check(
        "readiness: elapsed minutes computed from the two timestamps",
        readiness["elapsed_minutes"] is not None and abs(readiness["elapsed_minutes"] - 31.73) < 0.1,
    )

    unavailable_report = read_fixture("model-telemetry-readiness-unavailable.txt")
    unavailable = mt.parse_readiness_report(unavailable_report)
    check(
        "readiness: an unrecoverable Elapsed: line leaves elapsed_minutes as None, not a guess",
        unavailable["elapsed_minutes"] is None,
    )
    check("readiness: unavailable report still parses its provenance pair", unavailable["model"] == "claude-opus-5-5")

    # PR #405's own First-readiness report: "start:"/"ready:"/"elapsed:" and
    # a lowercase "head:" line, pre-dating both `provenance`'s block and the
    # "from claim (...) to first merge readiness (...)" sentence.
    old_report = read_fixture("model-telemetry-readiness-old.txt")
    old_readiness = mt.parse_readiness_report(old_report)
    check(
        "readiness: old start:/ready: shape still yields elapsed minutes",
        old_readiness["elapsed_minutes"] is not None and abs(old_readiness["elapsed_minutes"] - 13.07) < 0.1,
    )
    check(
        "readiness: old shape's lowercase head: line still parses",
        old_readiness["head_sha"] == "02105c85f47d7de4ecc83d34992472856b16d196",
    )
    check(
        "readiness: old shape's harness: line, past the session: line, still parses",
        old_readiness["harness"] == "Claude Code",
    )

    check(
        "find_readiness_report: matches on the leading marker",
        mt.find_readiness_report([{"body": good_report}]) is not None,
    )
    check(
        "find_readiness_report: a PR with no such comment returns None",
        mt.find_readiness_report([{"body": "some other comment"}]) is None,
    )

    # -- claim-versus-report model mismatch ----------------------------------
    claim_model = mt.parse_provenance_block(new_claim)["model"]
    report_model = mt.parse_readiness_report(unavailable_report)["model"]
    check(
        "claim-versus-report mismatch is a field, not silently resolved",
        claim_model != report_model,
    )
    check("is_model_mismatch: two different reported models is a mismatch", mt.is_model_mismatch("a", "b") is True)
    check("is_model_mismatch: the same model both places is not a mismatch", mt.is_model_mismatch("a", "a") is False)
    check(
        "is_model_mismatch: a claim with no readiness report is not a mismatch "
        "-- 'unreported' is a display placeholder, not the report's model",
        mt.is_model_mismatch("a", None) is False,
    )
    check("is_model_mismatch: no claim at all is not a mismatch", mt.is_model_mismatch(None, "b") is False)

    # -- review verification --------------------------------------------------
    review = read_fixture("model-telemetry-review-verification.txt")
    parsed_review = mt.parse_review_verification(review)
    check("review verification: parses at all", parsed_review is not None)
    if parsed_review:
        check("review verification: pass number", parsed_review["pass"] == 1)
        check("review verification: outcome", parsed_review["outcome"] == "clear")
        check("review verification: one finding line counted", parsed_review["findings_count"] == 1)

    clean_review = read_fixture("model-telemetry-review-verification-clean.txt")
    parsed_clean = mt.parse_review_verification(clean_review)
    check(
        "review verification: 'findings: none' counts zero, not one finding named none",
        parsed_clean is not None and parsed_clean["findings_count"] == 0,
    )

    check(
        "parse_review_verification: a comment with no marker returns None",
        mt.parse_review_verification("not a review verification comment") is None,
    )

    verifications = mt.parse_review_verifications([{"body": review}, {"body": clean_review}, {"body": "noise"}])
    check("parse_review_verifications: finds both passes, skips the noise", len(verifications) == 2)

    # -- check-run reruns -------------------------------------------------------
    reruns = mt.count_check_reruns(
        [
            {"name": "check-runtime"},
            {"name": "check-runtime"},
            {"name": "check-runtime"},
            {"name": "check-eval-tooling"},
        ]
    )
    check("count_check_reruns: two extra runs of the same name is two reruns", reruns == 2)
    check("count_check_reruns: no repeats is zero reruns", mt.count_check_reruns([{"name": "a"}, {"name": "b"}]) == 0)

    for token in ("mechanical", "implementation", "reasoning"):
        check(
            f"read_model_class: preserves {token}",
            mt.read_model_class(f"## Model class\n\n`{token}`\n") == token,
        )
    # Without this regression, frontier assignments disappear from telemetry as unlabelled.
    check(
        "read_model_class: preserves frontier as a class",
        mt.read_model_class("## Model class\n\n`frontier`\n") == "frontier",
    )
    check(
        "read_model_class: rejects a suffixed frontier token",
        mt.read_model_class("## Model class\n\n`frontier-extra`\n") == "unlabelled",
    )
    check(
        "read_model_class: a body with no section is unlabelled",
        mt.read_model_class("no section here") == "unlabelled",
    )
    check("closed_issue_number: reads a Closes #N line", mt.closed_issue_number("fixes bug\n\nCloses #361") == 361)
    check("closed_issue_number: a body naming no issue is None", mt.closed_issue_number("no issue line") is None)

    # -- the table renders without a repository walk -----------------------------
    table = mt.render_table(
        [
            {"model": "claude-sonnet-5", "elapsed_minutes": 30.0, "review_passes": 1, "findings_count": 1, "check_reruns": 0},
            {"model": "claude-sonnet-5", "elapsed_minutes": 50.0, "review_passes": 2, "findings_count": 0, "check_reruns": 1},
            {"model": "unreported", "elapsed_minutes": None, "review_passes": 1, "findings_count": 0, "check_reruns": 0},
        ]
    )
    check("render_table: names every model, sorted", table.index("claude-sonnet-5") < table.index("unreported"))
    check("render_table: a model with no elapsed time reads n/a, not a crash", "n/a" in table)

    if errors:
        print("model-telemetry check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print("model-telemetry: all fixture and unit checks pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())
