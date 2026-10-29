import pytest

from scripts.eval_endpoint import compute_percentile, estimate_muse_cost


def test_estimate_muse_cost_simple_examples():
    # 0 ms -> $0.0
    assert estimate_muse_cost(0) == 0.0

    # 999 ms -> rounds down to 0 whole seconds -> $0.0
    assert estimate_muse_cost(999) == 0.0

    # 1000 ms -> 1 whole second -> 1 * (0.003 / 60) = 0.00005
    assert pytest.approx(estimate_muse_cost(1000), rel=1e-6) == 0.00005

    # 1999 ms -> 1 whole second -> 0.00005
    assert pytest.approx(estimate_muse_cost(1999), rel=1e-6) == 0.00005

    # 60,000 ms (1 minute) -> 60 whole seconds -> 60 * (0.003 / 60) = 0.003
    assert pytest.approx(estimate_muse_cost(60000), rel=1e-6) == 0.003

    # 120,000 ms (2 minutes) -> 120 whole seconds -> 0.006
    assert pytest.approx(estimate_muse_cost(120000), rel=1e-6) == 0.006


def test_compute_percentile_simple_examples():
    # Empty list
    assert compute_percentile([], 50.0) == 0.0

    # Single value
    assert compute_percentile([42.0], 50.0) == 42.0
    assert compute_percentile([42.0], 95.0) == 42.0

    # Sorted list: [10, 20, 30, 40, 50]
    vals = [10.0, 20.0, 30.0, 40.0, 50.0]
    assert compute_percentile(vals, 0.0) == 10.0
    assert compute_percentile(vals, 50.0) == 30.0
    assert compute_percentile(vals, 100.0) == 50.0

    # Check p95 linear interpolation:
    # rank = 0.95 * 4 = 3.8 -> 40 * 0.2 + 50 * 0.8 = 48.0
    assert pytest.approx(compute_percentile(vals, 95.0), rel=1e-4) == 48.0
