"""Mann-Kendall + Sen's slope tests with hand-verified fixtures."""

import math

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
