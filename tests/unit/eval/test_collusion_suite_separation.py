"""Property: the suite separates colluding pairs from benign pairs.

Gates that admit one change at a time are blind to two tasks combining into
a violation; this test protects the measurement that the cross-task check
catches those combinations *without* rejecting honest co-changes — a false
positive here blocks legitimate merges.
"""

from bernstein.eval.bench.collusion_suite import load_cases, run_suite


def test_colluding_pairs_flagged_and_benign_pairs_pass():
    cases = load_cases()
    colluding = [c for c in cases if c.kind == "collusion"]
    benign = [c for c in cases if c.kind == "benign"]
    assert len(colluding) >= 5, "need at least 5 colluding pairs"
    assert len(benign) >= 5, "need at least 5 benign pairs"

    result = run_suite(cases)
    flagged = {r.case_id for r in result.results if r.actual == "flag"}
    passed = {r.case_id for r in result.results if r.actual == "pass"}

    assert {c.id for c in colluding} <= flagged
    assert {c.id for c in benign} <= passed

    score = result.score()
    assert score["false_positives"] == 0
    assert score["false_negatives"] == 0
