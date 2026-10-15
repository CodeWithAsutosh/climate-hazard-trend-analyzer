"""Normalize provider daily data into validated daily records."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date

PHYS_MIN_C = -90.0
PHYS_MAX_C = 60.0

FLAG_SUSPICIOUS = "suspicious_value"
FLAG_INVALID = "invalid"
FLAG_DUPLICATE_RESOLVED = "duplicate_resolved"
FLAG_INTERPOLATED_NEVER = "never_interpolated"


@dataclass
class DailyRecord:
    date: date
    tmax_c: float | None
    valid: bool
    flags: list[str] = field(default_factory=list)


def to_celsius(value: float, unit: str) -> float:
    u = unit.strip().lower()
    if u in {"c", "celsius", "°c", "degc"}:
        return float(value)
    if u in {"f", "fahrenheit", "°f", "degf"}:
        return (float(value) - 32.0) * 5.0 / 9.0
    if u in {"k", "kelvin"}:
        return float(value) - 273.15
    raise ValueError(f"unsupported temperature unit: {unit!r}")


def _parse_date(s: str) -> date | None:
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


def normalize_daily_series(
    dates: list[str],
    tmax_values: list[object],
    unit: str = "celsius",
) -> tuple[list[DailyRecord], dict]:
    """Normalize parallel date/value arrays.

    Rules: deterministic duplicate resolution (keep max valid), sort by date,
    preserve gaps, never interpolate, flag implausible values.
    """
    stats = {
        "input_rows": len(dates),
        "duplicates": 0,
        "invalid": 0,
        "out_of_order": 0,
        "suspicious": 0,
    }
    by_date: dict[date, list[float | None]] = {}
    ordered = list(zip(dates, tmax_values, strict=False))
    # detect out-of-order on raw input parseable dates
    parsed_seq: list[date] = []
    for ds, _ in ordered:
        d = _parse_date(str(ds)) if isinstance(ds, str) else None
        if d is not None:
            parsed_seq.append(d)
    for a, b in zip(parsed_seq, parsed_seq[1:], strict=False):
        if b < a:
            stats["out_of_order"] += 1
            break

    for ds, raw in ordered:
        d = _parse_date(str(ds)) if isinstance(ds, str) else None
        if d is None:
            stats["invalid"] += 1
            continue
        val: float | None = None
        invalid = False
        if raw is None:
            invalid = True
        elif isinstance(raw, bool):
            invalid = True
        elif isinstance(raw, int | float):
            f = float(raw)
            if not math.isfinite(f):
                invalid = True
            else:
                try:
                    val = to_celsius(f, unit)
                except ValueError:
                    invalid = True
        elif isinstance(raw, str):
            try:
                f = float(raw.strip())
                if not math.isfinite(f):
                    invalid = True
                else:
                    val = to_celsius(f, unit)
            except (ValueError, AttributeError):
                invalid = True
        else:
            invalid = True
        if invalid:
            by_date.setdefault(d, []).append(None)
        else:
            assert val is not None
            by_date.setdefault(d, []).append(val)

    records: list[DailyRecord] = []
    for d in sorted(by_date):
        vals = by_date[d]
        if len(vals) > 1:
            stats["duplicates"] += len(vals) - 1
        valid_vals = [v for v in vals if v is not None]
        flags: list[str] = []
        if len(vals) > 1:
            flags.append(FLAG_DUPLICATE_RESOLVED)
        if not valid_vals:
            stats["invalid"] += 1
            records.append(DailyRecord(date=d, tmax_c=None, valid=False, flags=[FLAG_INVALID]))
            continue
        # deterministic: keep maximum valid observation
        chosen = max(valid_vals)
        if chosen < PHYS_MIN_C or chosen > PHYS_MAX_C:
            stats["invalid"] += 1
            records.append(DailyRecord(date=d, tmax_c=None, valid=False, flags=[FLAG_INVALID]))
            continue
        # suspicious but usable: near-edge heat that deserves a flag
        if chosen > 50.0 or chosen < -60.0:
            flags.append(FLAG_SUSPICIOUS)
            stats["suspicious"] += 1
        records.append(DailyRecord(date=d, tmax_c=round(chosen, 2), valid=True, flags=flags))
    stats["output_days"] = len(records)
    stats["valid_days"] = sum(1 for r in records if r.valid)
    return records, stats
