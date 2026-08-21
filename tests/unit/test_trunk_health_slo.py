from scripts.trunk_health_slo import MIN_SAMPLE_SIZE, score_runs


def test_score_runs_counts_only_failures():
    runs = [
        {"conclusion": "success"},
        {"conclusion": "failure"},
        {"conclusion": "timed_out"},
        {"conclusion": "success"},
        {"conclusion": "cancelled"},  # excluded
        {"conclusion": "skipped"},  # excluded
        {"conclusion": None},  # excluded (in-progress)
    ]
    total, red, red_pct = score_runs(runs)
    # 7 input, 3 excluded -> 4 total
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


def test_score_runs_integer_floor():
    # 1 red out of 3 total = 33.33% -> should floor to 33%
    runs = [
        {"conclusion": "failure"},
        {"conclusion": "success"},
        {"conclusion": "success"},
    ]
    total, red, red_pct = score_runs(runs)
    assert total == 3
    assert red == 1
    assert red_pct == 33


def test_insufficient_sample_boundary():
    # MIN_SAMPLE_SIZE - 1 should be insufficient (handled by main, but test the score)
    runs = [{"conclusion": "success"} for _ in range(MIN_SAMPLE_SIZE - 1)]
    total, red, red_pct = score_runs(runs)
    assert total == MIN_SAMPLE_SIZE - 1
    assert red == 0
    assert red_pct == 0
