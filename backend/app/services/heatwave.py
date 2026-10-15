"""Heatwave detection: >=3 consecutive valid days with tmax > p95 baseline.

Methodology (documented, deterministic):
- Threshold = 95th percentile (linear interpolation, numpy 'linear' method
  equivalent) of valid daily tmax in the fixed baseline period.
- Threshold is constant year-round (non-seasonal); disclosed in API + README.
- Strict comparison: hot iff tmax_c > threshold.
- Missing/invalid day or calendar gap breaks a run.
- Event = maximal run with length >= 3. Duration = run length.
- Per-day intensity = tmax_c - threshold. Per-event intensity_mean/max defined
  from those exceedances. Annual intensity = mean of event means (and max of
  event maxes).
- Event year assignment: year of event start date (documented convention).
- Feb 29 is treated as an ordinary calendar day; baseline uses all valid
  baseline days including leap days.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from app.services.normalization import DailyRecord

MIN_CONSECUTIVE_DAYS = 3
THRESHOLD_PERCENTILE = 95.0
MIN_BASELINE_OBSERVATIONS = 100


@dataclass
class HeatwaveEvent:
    start: date
    end: date
    duration_days: int
    intensity_mean_c: float
    intensity_max_c: float
    year: int  # year of start


def percentile_linear(values: list[float], pct: float) -> float:
    """Linear-interpolation percentile (0-100), matches numpy default."""
    if not values:
        raise ValueError("no values for percentile")
    if not (0 <= pct <= 100):
        raise ValueError("percentile must be within 0..100")
    s = sorted(values)
    n = len(s)
    if n == 1:
        return float(s[0])
    rank = (pct / 100.0) * (n - 1)
    lo = int(rank)
    hi = min(lo + 1, n - 1)
    frac = rank - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)


def compute_threshold(
    records: list[DailyRecord],
    baseline_start: date,
    baseline_end: date,
    percentile: float = THRESHOLD_PERCENTILE,
) -> tuple[float | None, int, str | None]:
    vals = [
        r.tmax_c
        for r in records
        if r.valid and r.tmax_c is not None and baseline_start <= r.date <= baseline_end
    ]
    if len(vals) < MIN_BASELINE_OBSERVATIONS:
        return None, len(vals), "insufficient_baseline_observations"
    return round(percentile_linear(vals, percentile), 2), len(vals), None


def detect_heatwaves(records: list[DailyRecord], threshold_c: float) -> list[HeatwaveEvent]:
    events: list[HeatwaveEvent] = []
    run: list[DailyRecord] = []
    prev: date | None = None
    for r in sorted(records, key=lambda x: x.date):
        hot = r.valid and r.tmax_c is not None and r.tmax_c > threshold_c
        consecutive = prev is not None and (r.date - prev).days == 1
        if hot and (not run or consecutive):
            # Continue or start a run (a hot day always starts a run when empty;
            # a gap with a non-empty run is handled in the else branch).
            run.append(r)
        else:
            if len(run) >= MIN_CONSECUTIVE_DAYS:
                events.append(_close_run(run, threshold_c))
            # A hot day after a gap/non-hot day starts a fresh run.
            run = [r] if hot else []
        prev = r.date
    if len(run) >= MIN_CONSECUTIVE_DAYS:
        events.append(_close_run(run, threshold_c))
    return events


def _close_run(run: list[DailyRecord], threshold_c: float) -> HeatwaveEvent:
    exceed = [(r.tmax_c - threshold_c) for r in run if r.tmax_c is not None]
    mean_ex = round(sum(exceed) / len(exceed), 2) if exceed else 0.0
    max_ex = round(max(exceed), 2) if exceed else 0.0
    return HeatwaveEvent(
        start=run[0].date,
        end=run[-1].date,
        duration_days=len(run),
        intensity_mean_c=mean_ex,
        intensity_max_c=max_ex,
        year=run[0].date.year,
    )
