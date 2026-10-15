"""Annual aggregation, OLS trend, early/late percentage change, Mann-Kendall."""

from __future__ import annotations

import calendar
import math
from datetime import date

from app.services.heatwave import HeatwaveEvent
from app.services.normalization import DailyRecord

MIN_YEAR_COVERAGE = 0.8  # project assumption, documented
COVERAGE_WARNING_LEVEL = 0.9
MIN_VALID_YEARS_FOR_TREND = 5
MIN_VALID_FRACTION_FOR_TREND = 0.7
MK_ALPHA = 0.05
MK_MIN_N = 4

TREND_METHOD = (
    "ordinary-least-squares slope on annual heatwave event counts (valid-coverage "
    "years only); change_percent compares mean of late-half years vs mean of "
    "early-half years: 100*(late-early)/early; undefined when early mean is 0; "
    "Mann-Kendall test (two-sided, normal approximation with tie correction, "
    "alpha=0.05) plus Sen's slope on the same series"
)


def mann_kendall(values: list[float]) -> dict:
    """Mann-Kendall trend test (two-sided) with tie correction + Sen's slope.

    Pure-Python implementation of the standard test:
    S = sum(sign(xj - xi)); Var(S) with tie correction; z with continuity
    correction; p from the standard normal CDF. Returns an insufficient_data
    marker when n < 4. For n < 8 the normal approximation is rough and a
    caveat is included.
    """
    n = len(values)
    base = {
        "alpha": MK_ALPHA,
        "n": n,
    }
    if n < MK_MIN_N or any(not math.isfinite(v) for v in values):
        return {
            **base,
            "trend": "insufficient_data",
            "s": None,
            "p_value": None,
            "sens_slope_per_year": None,
            "caveats": ["fewer than 4 observations; Mann-Kendall not computed"],
        }
    s = 0
    for i in range(n):
        for j in range(i + 1, n):
            if values[j] > values[i]:
                s += 1
            elif values[j] < values[i]:
                s -= 1
    # tie correction: sum over tied groups of t(t-1)(2t+5)
    tie_sum = 0
    counts: dict[float, int] = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    for t in counts.values():
        if t > 1:
            tie_sum += t * (t - 1) * (2 * t + 5)
    var = (n * (n - 1) * (2 * n + 5) - tie_sum) / 18.0
    if var <= 0:
        z, p = 0.0, 1.0
    else:
        sd = math.sqrt(var)
        if s > 0:
            z = (s - 1) / sd
        elif s < 0:
            z = (s + 1) / sd
        else:
            z = 0.0
        phi = 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0)))
        p = round(max(0.0, min(1.0, 2.0 * (1.0 - phi))), 4)
        z = round(z, 4)
    if p < MK_ALPHA and s > 0:
        trend = "increasing"
    elif p < MK_ALPHA and s < 0:
        trend = "decreasing"
    else:
        trend = "no_trend"
    # Sen's slope: median of pairwise slopes per unit index step
    slopes = sorted(
        (values[j] - values[i]) / (j - i) for i in range(n) for j in range(i + 1, n)
    )
    m = len(slopes)
    sens = slopes[m // 2] if m % 2 == 1 else (slopes[m // 2 - 1] + slopes[m // 2]) / 2
    caveats = []
    if n < 8:
        caveats.append("fewer than 8 observations; normal approximation is rough")
    return {
        **base,
        "trend": trend,
        "s": s,
        "z": z if var > 0 else 0.0,
        "p_value": p,
        "sens_slope_per_year": round(sens, 4),
        "caveats": caveats,
    }


def expected_days(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def aggregate_annual(
    records: list[DailyRecord],
    events: list[HeatwaveEvent],
    start_year: int,
    end_year: int,
) -> tuple[list[dict], dict]:
    by_date = {r.date: r for r in records}
    by_year_events: dict[int, list[HeatwaveEvent]] = {}
    for e in events:
        by_year_events.setdefault(e.year, []).append(e)
    annual: list[dict] = []
    missing_days_total = 0
    warnings: list[str] = []
    coverage_by_year: list[dict] = []
    for year in range(start_year, end_year + 1):
        valid = 0
        for d_ord in range(1, expected_days(year) + 1):
            d = date(year, 1, 1).fromordinal(date(year, 1, 1).toordinal() + d_ord - 1)
            rec = by_date.get(d)
            if rec is not None and rec.valid:
                valid += 1
        exp = expected_days(year)
        cov = round(valid / exp, 4) if exp else 0.0
        missing = exp - valid
        missing_days_total += missing
        sufficient = cov >= MIN_YEAR_COVERAGE
        evs = [e for e in by_year_events.get(year, []) if True]
        # only count events in sufficient-coverage years for annual display?
        # No: display all events but flag coverage; trend uses sufficient years only.
        count = len(evs)
        total_days = sum(e.duration_days for e in evs)
        if evs:
            mean_dur = round(sum(e.duration_days for e in evs) / len(evs), 2)
            max_dur = max(e.duration_days for e in evs)
            mean_int = round(sum(e.intensity_mean_c for e in evs) / len(evs), 2)
            max_int = round(max(e.intensity_max_c for e in evs), 2)
        else:
            mean_dur = None
            max_dur = None
            mean_int = None
            max_int = None
        if not sufficient:
            warnings.append(
                f"{year}: low data coverage {cov:.1%} below {MIN_YEAR_COVERAGE:.0%} minimum"
            )
        elif cov < COVERAGE_WARNING_LEVEL:
            warnings.append(
                f"{year}: coverage {cov:.1%} below {COVERAGE_WARNING_LEVEL:.0%} advisory level"
            )
        coverage_by_year.append({"year": year, "coverage": cov, "sufficient": sufficient})
        annual.append(
            {
                "year": year,
                "event_count": count,
                "total_heatwave_days": total_days,
                "mean_duration_days": mean_dur,
                "max_duration_days": max_dur,
                "mean_intensity_c": mean_int,
                "max_intensity_c": max_int,
                "coverage_fraction": cov,
                "sufficient_coverage": sufficient,
            }
        )
    quality = {
        "coverage_by_year": coverage_by_year,
        "missing_days": missing_days_total,
        "warnings": warnings,
    }
    return annual, quality


def ols_slope(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    denom = sum((x - mx) ** 2 for x in xs)
    if denom == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False)) / denom


def compute_trend(annual: list[dict]) -> dict:
    usable = [a for a in annual if a.get("sufficient_coverage")]
    mk = mann_kendall([float(a["event_count"]) for a in usable])
    caveats: list[str] = []
    if len(usable) < MIN_VALID_YEARS_FOR_TREND or (
        len(annual) and len(usable) / len(annual) < MIN_VALID_FRACTION_FOR_TREND
    ):
        return {
            "direction": "insufficient_data",
            "slope_events_per_year": None,
            "method": TREND_METHOD,
            "early_period": None,
            "late_period": None,
            "change_percent": None,
            "change_percent_calculable": False,
            "caveats": ["insufficient years with adequate data coverage for a trend estimate"],
            "mann_kendall": mk,
        }
    xs = [float(a["year"]) for a in usable]
    ys = [float(a["event_count"]) for a in usable]
    if any(not math.isfinite(v) for v in ys) or any(v < 0 for v in ys):
        return {
            "direction": "insufficient_data",
            "slope_events_per_year": None,
            "method": TREND_METHOD,
            "early_period": None,
            "late_period": None,
            "change_percent": None,
            "change_percent_calculable": False,
            "caveats": ["non-finite or negative counts; cannot compute trend"],
            "mann_kendall": mk,
        }
    slope = ols_slope(xs, ys)
    slope_r = round(slope, 4) if slope is not None else None
    half = len(usable) // 2
    if half == 0:
        return {
            "direction": "insufficient_data",
            "slope_events_per_year": slope_r,
            "method": TREND_METHOD,
            "early_period": None,
            "late_period": None,
            "change_percent": None,
            "change_percent_calculable": False,
            "caveats": ["too few years to split early/late periods"],
            "mann_kendall": mk,
        }
    early = usable[:half]
    late = usable[len(usable) - half :]
    early_mean = sum(a["event_count"] for a in early) / len(early)
    late_mean = sum(a["event_count"] for a in late) / len(late)
    early_period = {
        "start_year": early[0]["year"],
        "end_year": early[-1]["year"],
        "mean_events": round(early_mean, 3),
    }
    late_period = {
        "start_year": late[0]["year"],
        "end_year": late[-1]["year"],
        "mean_events": round(late_mean, 3),
    }
    if early_mean == 0:
        change = None
        calculable = False
        caveats.append("early-period mean is zero; percentage change is undefined")
    else:
        change = round(100.0 * (late_mean - early_mean) / early_mean, 2)
        calculable = True
    if slope is None:
        direction = "insufficient_data"
    elif slope > 0.01:
        direction = "increasing"
    elif slope < -0.01:
        direction = "decreasing"
    else:
        direction = "no_clear_trend"
    if all(y == 0 for y in ys):
        caveats.append("all annual counts are zero; no trend is detectable")
    caveats.append("descriptive trend only; this analysis alone does not establish causation")
    caveats.extend(mk.get("caveats", []))
    return {
        "direction": direction,
        "slope_events_per_year": slope_r,
        "method": TREND_METHOD,
        "early_period": early_period,
        "late_period": late_period,
        "change_percent": change,
        "change_percent_calculable": calculable,
        "caveats": caveats,
        "mann_kendall": mk,
    }
