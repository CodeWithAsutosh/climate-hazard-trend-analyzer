"""Unit tests for percentile + heatwave detection (hand-verified fixtures)."""

from datetime import date, timedelta

import pytest

from app.services.heatwave import (
    compute_threshold,
    detect_heatwaves,
    percentile_linear,
)
from app.services.normalization import DailyRecord


def dr(day: date, t: float | None) -> DailyRecord:
    if t is None:
        return DailyRecord(date=day, tmax_c=None, valid=False, flags=["invalid"])
    return DailyRecord(date=day, tmax_c=t, valid=True, flags=[])


def series(start: date, temps: list[float | None]) -> list[DailyRecord]:
    return [dr(start + timedelta(days=i), t) for i, t in enumerate(temps)]


def test_percentile_linear_known_values():
    # 1..100 -> p95 = 95.05 by linear interpolation: rank=0.95*99=94.05
    vals = [float(i) for i in range(1, 101)]
    assert percentile_linear(vals, 95) == pytest.approx(95.05)
    assert percentile_linear([5.0], 95) == 5.0
    assert percentile_linear([1.0, 3.0], 50) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        percentile_linear([], 95)


def test_zero_qualifying_days_no_event():
    recs = series(date(2020, 6, 1), [20.0, 21.0, 22.0, 20.0])
    assert detect_heatwaves(recs, 25.0) == []


def test_two_consecutive_hot_days_no_event():
    recs = series(date(2020, 6, 1), [20.0, 30.0, 31.0, 20.0])
    assert detect_heatwaves(recs, 25.0) == []


def test_exactly_three_hot_days_one_event():
    recs = series(date(2020, 6, 1), [20.0, 30.0, 31.0, 32.0, 20.0])
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1
    assert evs[0].duration_days == 3
    assert evs[0].start == date(2020, 6, 2)
    assert evs[0].end == date(2020, 6, 4)
    # intensity = mean exceedance above 25
    assert evs[0].intensity_mean_c == pytest.approx((5 + 6 + 7) / 3)
    assert evs[0].intensity_max_c == pytest.approx(7.0)


def test_five_day_run_is_single_event():
    recs = series(date(2020, 6, 1), [30.0, 31.0, 32.0, 33.0, 34.0])
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1 and evs[0].duration_days == 5


def test_ten_day_run_is_single_event():
    recs = series(date(2020, 6, 1), [30.0] * 10)
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1 and evs[0].duration_days == 10


def test_two_events_separated_by_cool_day():
    recs = series(date(2020, 6, 1), [30.0, 31.0, 32.0, 20.0, 33.0, 34.0, 35.0, 20.0])
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 2
    assert [e.duration_days for e in evs] == [3, 3]


def test_missing_day_splits_run():
    recs = series(date(2020, 6, 1), [30.0, 31.0, None, 32.0, 33.0, 34.0])
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1  # only the trailing 3-day run counts
    assert evs[0].start == date(2020, 6, 4)


def test_calendar_gap_splits_run():
    # dates skip 2020-06-03 entirely
    recs = [
        dr(date(2020, 6, 1), 30.0),
        dr(date(2020, 6, 2), 31.0),
        dr(date(2020, 6, 4), 32.0),
        dr(date(2020, 6, 5), 33.0),
        dr(date(2020, 6, 6), 34.0),
    ]
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1
    assert evs[0].duration_days == 3


def test_threshold_equality_not_hot():
    recs = series(date(2020, 6, 1), [25.0, 25.0, 25.0, 25.0])
    assert detect_heatwaves(recs, 25.0) == []


def test_just_above_and_below_threshold():
    recs = series(date(2020, 6, 1), [24.99, 25.01, 25.02, 25.03, 24.99])
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1 and evs[0].duration_days == 3


def test_event_crossing_year_boundary_assigned_to_start_year():
    recs = [
        dr(date(2020, 12, 30), 30.0),
        dr(date(2020, 12, 31), 31.0),
        dr(date(2021, 1, 1), 32.0),
        dr(date(2021, 1, 2), 20.0),
    ]
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1
    assert evs[0].year == 2020
    assert evs[0].duration_days == 3


def test_empty_input_no_events():
    assert detect_heatwaves([], 25.0) == []


def test_insufficient_baseline_flagged():
    recs = series(date(2020, 1, 1), [20.0] * 10)
    thr, n, err = compute_threshold(recs, date(2020, 1, 1), date(2020, 12, 31))
    assert thr is None and err == "insufficient_baseline_observations"
    assert n == 10


def test_threshold_deterministic_fixture():
    # 200 baseline days: 0..199 -> p95 linear = rank 0.95*199 = 189.05 -> 189.05
    start = date(2000, 1, 1)
    recs = [dr(start + timedelta(days=i), float(i)) for i in range(200)]
    thr, n, err = compute_threshold(recs, start, start + timedelta(days=300))
    assert err is None and n == 200
    assert thr == pytest.approx(189.05)


def test_determinism_repeated_runs():
    recs = series(date(2020, 6, 1), [30.0, 31.0, 32.0, 20.0, 33.0, 34.0, 35.0])
    a = detect_heatwaves(recs, 25.0)
    b = detect_heatwaves(list(recs), 25.0)
    assert [(e.start, e.end) for e in a] == [(e.start, e.end) for e in b]


def test_invalid_between_valid_breaks_run():
    recs = series(date(2020, 6, 1), [30.0, 31.0, 32.0, None, None, None])
    # leading 3-day run still counts even if followed by invalid days
    evs = detect_heatwaves(recs, 25.0)
    assert len(evs) == 1 and evs[0].duration_days == 3
