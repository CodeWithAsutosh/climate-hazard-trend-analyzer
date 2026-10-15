"""Normalization unit tests: units, duplicates, gaps, plausibility."""

from datetime import date

from app.services.normalization import normalize_daily_series, to_celsius


def test_celsius_passthrough():
    recs, _ = normalize_daily_series(["2020-01-01"], [20.5], "celsius")
    assert recs[0].tmax_c == 20.5 and recs[0].valid


def test_fahrenheit_conversion():
    assert to_celsius(32.0, "fahrenheit") == 0.0
    assert to_celsius(212.0, "fahrenheit") == 100.0
    recs, _ = normalize_daily_series(["2020-01-01"], [77.0], "fahrenheit")
    assert recs[0].tmax_c == 25.0


def test_kelvin_conversion():
    assert to_celsius(273.15, "kelvin") == 0.0


def test_unsupported_unit_rejected():
    recs, _ = normalize_daily_series(["2020-01-01"], [20.0], "rankine")
    assert not recs[0].valid


def test_duplicate_dates_keep_max_deterministically():
    recs, stats = normalize_daily_series(
        ["2020-01-01", "2020-01-01", "2020-01-01"], [20.0, 25.0, 22.0], "celsius"
    )
    assert len(recs) == 1
    assert recs[0].tmax_c == 25.0
    assert stats["duplicates"] == 2
    assert "duplicate_resolved" in recs[0].flags


def test_duplicate_with_one_invalid_keeps_valid():
    recs, _ = normalize_daily_series(["2020-01-01", "2020-01-01"], [None, 22.0])
    assert len(recs) == 1 and recs[0].valid and recs[0].tmax_c == 22.0


def test_out_of_order_sorted():
    recs, stats = normalize_daily_series(
        ["2020-01-03", "2020-01-01", "2020-01-02"], [3.0, 1.0, 2.0]
    )
    assert [r.date for r in recs] == [date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3)]
    assert stats["out_of_order"] == 1


def test_missing_dates_preserved_as_gaps():
    recs, _ = normalize_daily_series(["2020-01-01", "2020-01-03"], [20.0, 21.0])
    assert len(recs) == 2  # gap date absent, not interpolated


def test_null_non_numeric_nan_invalid():
    import math

    recs, stats = normalize_daily_series(
        ["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-04", "2020-01-05"],
        [None, "abc", math.nan, math.inf, True],
    )
    assert all(not r.valid for r in recs)
    assert stats["invalid"] >= 5


def test_implausible_values_invalid():
    recs, _ = normalize_daily_series(["2020-01-01", "2020-01-02"], [100.0, -100.0])
    assert all(not r.valid for r in recs)


def test_leap_day_handled():
    recs, _ = normalize_daily_series(
        ["2020-02-28", "2020-02-29", "2020-03-01"], [20.0, 21.0, 22.0]
    )
    assert [r.date.isoformat() for r in recs] == [
        "2020-02-28",
        "2020-02-29",
        "2020-03-01",
    ]


def test_malformed_date_skipped():
    recs, stats = normalize_daily_series(["not-a-date", "2020-01-01"], [20.0, 21.0])
    assert len(recs) == 1 and recs[0].date == date(2020, 1, 1)
