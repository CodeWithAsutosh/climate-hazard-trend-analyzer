"""Mann-Kendall + Sen's slope tests with hand-verified fixtures."""

import math

import pytest

from app.services.trends import compute_trend, mann_kendall


def test_strictly_increasing():
    mk = mann_kendall([1.0, 2.0, 3.0, 4.0, 5.0])
    # hand-verified: S=10 pairs; Var=5*4*15/18=16.667; z=9/4.0825=2.2045
    assert mk["s"] == 10
    assert mk["z"] == round(9 / math.sqrt(300 / 18), 4)
    assert mk["p_value"] == 0.0275
    assert mk["trend"] == "increasing"
    assert mk["sens_slope_per_year"] == 1.0
    assert mk["n"] == 5


def test_strictly_decreasing():
    mk = mann_kendall([5.0, 4.0, 3.0, 2.0, 1.0])
    assert mk["s"] == -10
    assert mk["trend"] == "decreasing"
    assert mk["p_value"] == 0.0275
    assert mk["sens_slope_per_year"] == -1.0


def test_all_tied_no_trend():
    mk = mann_kendall([2.0, 2.0, 2.0, 2.0, 2.0])
    # tie group t=5 cancels variance to zero
    assert mk["s"] == 0
    assert mk["p_value"] == 1.0
    assert mk["trend"] == "no_trend"
    assert mk["sens_slope_per_year"] == 0.0


def test_tied_groups_correction():
    mk = mann_kendall([1.0, 1.0, 2.0, 2.0, 3.0, 3.0])
    # hand-verified: S=12 positive pairs; Var=(6*5*17-3*18)/18=25.333
    assert mk["s"] == 12
    assert mk["trend"] == "increasing"
    assert 0.02 < mk["p_value"] < 0.04
    assert mk["sens_slope_per_year"] > 0


def test_insufficient_observations():
    mk = mann_kendall([3.0, 1.0])
    assert mk["trend"] == "insufficient_data"
    assert mk["s"] is None and mk["p_value"] is None
    assert mann_kendall([])["trend"] == "insufficient_data"


def test_sens_slope_uses_year_gaps_not_sample_index():
    # Usable years are two years apart and counts rise by one each time, i.e.
    # 0.5 events/year. Index-step math would wrongly report 1.0.
    values = [0.0, 1.0, 2.0, 3.0]
    assert mann_kendall(values, [2000, 2002, 2004, 2006])["sens_slope_per_year"] == 0.5
    assert mann_kendall(values)["sens_slope_per_year"] == 1.0


def test_mann_kendall_rejects_mismatched_or_unsorted_years():
    with pytest.raises(ValueError):
        mann_kendall([1.0, 2.0, 3.0], [2000, 2001])
    with pytest.raises(ValueError):
        mann_kendall([1.0, 2.0, 3.0], [2001, 2000, 2002])


def test_compute_trend_sens_slope_uses_calendar_years():
    # 2003 and 2006 dropped for low coverage: 8 of 10 years usable (>= 70%).
    annual = [
        {
            "year": year,
            "event_count": i,
            "total_heatwave_days": i,
            "mean_duration_days": None,
            "max_duration_days": None,
            "mean_intensity_c": None,
            "max_intensity_c": None,
            "coverage_fraction": 1.0 if year not in (2003, 2006) else 0.5,
            "sufficient_coverage": year not in (2003, 2006),
        }
        for i, year in enumerate(range(2000, 2010))
    ]
    usable = [a for a in annual if a["sufficient_coverage"]]
    t = compute_trend(annual)
    # The trend is wired to pass years, so the gap-aware median applies...
    assert (
        t["mann_kendall"]["sens_slope_per_year"]
        == mann_kendall(
            [float(a["event_count"]) for a in usable],
            [a["year"] for a in usable],
        )["sens_slope_per_year"]
    )
    # ...and differs from the index-step value that ignored the dropped years.
    assert (
        t["mann_kendall"]["sens_slope_per_year"]
        != mann_kendall([float(a["event_count"]) for a in usable])["sens_slope_per_year"]
    )


def test_nonfinite_rejected():
    assert mann_kendall([1.0, 2.0, float("nan"), 4.0])["trend"] == "insufficient_data"


def test_compute_trend_carries_mann_kendall():
    annual = [
        {
            "year": 2000 + i,
            "event_count": i,
            "total_heatwave_days": i,
            "mean_duration_days": None,
            "max_duration_days": None,
            "mean_intensity_c": None,
            "max_intensity_c": None,
            "coverage_fraction": 1.0,
            "sufficient_coverage": True,
        }
        for i in range(6)
    ]
    t = compute_trend(annual)
    assert t["mann_kendall"]["trend"] == "increasing"
    assert t["mann_kendall"]["s"] == 15  # all C(6,2) pairs positive
