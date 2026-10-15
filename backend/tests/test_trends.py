"""Trend calculation tests: slopes, edge cases, percentage-change formula."""

from app.services.trends import compute_trend, ols_slope


def annual(counts: list[int], start: int = 2000) -> list[dict]:
    return [
        {
            "year": start + i,
            "event_count": c,
            "total_heatwave_days": c * 3,
            "mean_duration_days": 3.0 if c else None,
            "max_duration_days": 3 if c else None,
            "mean_intensity_c": 1.0 if c else None,
            "max_intensity_c": 1.0 if c else None,
            "coverage_fraction": 1.0,
            "sufficient_coverage": True,
        }
        for i, c in enumerate(counts)
    ]


def test_increasing_series():
    t = compute_trend(annual([0, 0, 1, 1, 2, 2, 3, 3]))
    assert t["direction"] == "increasing"
    assert t["slope_events_per_year"] is not None and t["slope_events_per_year"] > 0
    # early mean = (0+0+1+1)/4 = .5 ; late mean = (2+2+3+3)/4 = 2.5 -> +400%
    assert t["change_percent"] == 400.0
    assert t["early_period"] == {"start_year": 2000, "end_year": 2003, "mean_events": 0.5}
    assert t["late_period"] == {"start_year": 2004, "end_year": 2007, "mean_events": 2.5}


def test_decreasing_series():
    t = compute_trend(annual([3, 3, 2, 2, 1, 1, 0, 0]))
    assert t["direction"] == "decreasing"
    assert t["change_percent"] == -80.0  # (0.5-2.5)/2.5


def test_flat_series_no_clear_trend():
    t = compute_trend(annual([2, 2, 2, 2, 2, 2]))
    assert t["direction"] == "no_clear_trend"
    assert t["change_percent"] == 0.0


def test_all_zero_counts():
    t = compute_trend(annual([0, 0, 0, 0, 0, 0]))
    assert t["direction"] == "no_clear_trend"
    assert t["change_percent"] is None
    assert t["change_percent_calculable"] is False


def test_zero_early_mean_undefined():
    t = compute_trend(annual([0, 0, 0, 0, 1, 1, 1, 1]))
    assert t["change_percent"] is None
    assert t["change_percent_calculable"] is False


def test_insufficient_years():
    t = compute_trend(annual([1, 2, 3]))
    assert t["direction"] == "insufficient_data"


def test_low_coverage_excluded():
    rows = annual([5, 5, 5, 5, 5, 5])
    for r in rows[:4]:
        r["sufficient_coverage"] = False
        r["coverage_fraction"] = 0.1
    t = compute_trend(rows)
    assert t["direction"] == "insufficient_data"


def test_ols_slope_basic():
    assert ols_slope([1, 2, 3], [2, 4, 6]) == 2.0
    assert ols_slope([5], [1]) is None
    assert ols_slope([1, 1, 1], [1, 2, 3]) is None


def test_negative_counts_rejected():
    rows = annual([1, 1, 1, 1, 1, 1])
    rows[0]["event_count"] = -1
    t = compute_trend(rows)
    assert t["direction"] == "insufficient_data"
