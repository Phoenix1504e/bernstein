from scripts.trunk_health_slo import score_runs


def test_score_runs_counts_only_failures():
    runs = [
        {"conclusion": "success"},
        {"conclusion": "failure"},
        {"conclusion": "timed_out"},
        {"conclusion": "success"},
        {"conclusion": "cancelled"},  # excluded
        {"conclusion": "skipped"},  # excluded
    ]
    total, red, red_pct = score_runs(runs)
    # 6 input, 2 excluded -> 4 total
    # 2 red (failure, timed_out)
    # 2/4 = 50%
    assert total == 4
    assert red == 2
    assert red_pct == 50


def test_score_runs_empty():
    runs = []
    total, red, red_pct = score_runs(runs)
    assert total == 0
    assert red == 0
    assert red_pct == 0


def test_score_runs_all_success():
    runs = [
        {"conclusion": "success"},
        {"conclusion": "success"},
    ]
    total, red, red_pct = score_runs(runs)
    assert total == 2
    assert red == 0
    assert red_pct == 0
