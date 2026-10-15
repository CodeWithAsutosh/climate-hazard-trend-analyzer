"""Orchestrates cache lookup, provider fetch, normalization, analysis."""

from __future__ import annotations

import time
from datetime import date

from app.config import Settings
from app.repositories.store import HybridStore
from app.schemas.analysis import AnalysisRequest, BBoxRegion, PointRegion
from app.services import heatwave as hw
from app.services import trends as tr
from app.services.cache_key import build_cache_key
from app.services.normalization import normalize_daily_series
from app.services.weather_client import ProviderError, fetch_daily_max


def resolve_point(req: AnalysisRequest) -> tuple[float, float, dict]:
    r = req.region
    if isinstance(r, PointRegion):
        return (
            round(float(r.latitude), 4),
            round(float(r.longitude), 4),
            {
                "type": "point",
                "latitude": round(float(r.latitude), 4),
                "longitude": round(float(r.longitude), 4),
            },
        )
    assert isinstance(r, BBoxRegion)
    centroid = r.centroid
    return (
        centroid[0],
        centroid[1],
        {
            "type": "bbox",
            "min_lat": float(r.min_lat),
            "max_lat": float(r.max_lat),
            "min_lon": float(r.min_lon),
            "max_lon": float(r.max_lon),
            "centroid": {"latitude": centroid[0], "longitude": centroid[1]},
            "aggregation": "centroid-grid-cell (bbox approximated by its centroid)",
        },
    )


async def run_analysis(req: AnalysisRequest, settings: Settings, store: HybridStore) -> dict:
    lat, lon, region_out = resolve_point(req)
    location_key = f"{lat:.4f},{lon:.4f}"
    cache_key = build_cache_key(
        req.region,
        req.start_year,
        req.end_year,
        req.baseline_start_year,
        req.baseline_end_year,
        settings.algorithm_version,
        settings.provider_dataset_version,
    )
    now = time.time()
    cached = store.get_cache(cache_key, now)
    if cached is not None and isinstance(cached.get("result"), dict):
        result = dict(cached["result"])
        result["cache"] = {"status": "hit", "key": cache_key[:12]}
        return result

    # baseline may extend beyond analysis period: fetch union range
    fetch_start_year = min(req.start_year, req.baseline_start_year)
    fetch_end_year = max(req.end_year, req.baseline_end_year)
    fetch_start = f"{fetch_start_year}-01-01"
    fetch_end = f"{fetch_end_year}-12-31"

    provider = await fetch_daily_max(
        settings.weather_provider_base_url,
        lat,
        lon,
        fetch_start,
        fetch_end,
        settings.weather_connect_timeout_s,
        settings.weather_read_timeout_s,
        settings.weather_max_response_bytes,
    )
    records, norm_stats = normalize_daily_series(provider.dates, provider.tmax, provider.unit)

    # persist normalized daily docs (best effort)
    docs = [
        {
            "provider": "open-meteo",
            "location_key": location_key,
            "date": r.date.isoformat(),
            "tmax_c": r.tmax_c,
            "valid": r.valid,
            "quality_flags": r.flags,
            "fetched_at": now,
            "source_metadata": provider.source_metadata,
        }
        for r in records
    ]
    try:
        store.upsert_daily(docs)
    except Exception:
        pass

    threshold, n_base, base_err = hw.compute_threshold(
        records, date(req.baseline_start_year, 1, 1), date(req.baseline_end_year, 12, 31)
    )
    if threshold is None:
        raise ProviderError(
            f"insufficient baseline observations ({n_base}); "
            f"need >= {hw.MIN_BASELINE_OBSERVATIONS} valid days",
            422,
            False,
        )
    events = hw.detect_heatwaves(records, threshold)
    # restrict events to analysis period for annual table (baseline may be wider)
    events = [e for e in events if req.start_year <= e.year <= req.end_year]
    annual, quality = tr.aggregate_annual(records, events, req.start_year, req.end_year)
    summary = tr.compute_trend(annual)

    quality["warnings"] = list(quality.get("warnings", []))
    if getattr(req.region, "type", None) == "bbox":
        quality["warnings"].insert(
            0,
            "bbox approximated by its centroid grid cell; "
            "one point does not represent the whole region",
        )
    quality["normalization"] = norm_stats

    result = {
        "hazard": "heatwave",
        "region": region_out,
        "period": {"start_year": req.start_year, "end_year": req.end_year},
        "definition": {
            "variable": "daily_maximum_temperature",
            "threshold_percentile": 95,
            "percentile_method": (
                "linear interpolation (numpy-linear equivalent); constant year-round threshold"
            ),
            "minimum_consecutive_days": 3,
            "comparison": "strictly greater than threshold (tmax > threshold)",
            "baseline_period": {
                "start_year": req.baseline_start_year,
                "end_year": req.baseline_end_year,
            },
            "event_year_assignment": "year of event start date",
            "missing_data_rule": (
                "missing/invalid day or calendar gap breaks a run; never interpolated"
            ),
            "intensity_definition": (
                "per-day exceedance tmax-threshold; event mean/max; annual mean of event means"
            ),
            "minimum_coverage_fraction": tr.MIN_YEAR_COVERAGE,
            "trend_method": tr.TREND_METHOD,
            "algorithm_version": settings.algorithm_version,
        },
        "threshold_c": threshold,
        "baseline_observations": n_base,
        "annual": annual,
        "summary": summary,
        "quality": quality,
        "source": {
            **provider.source_metadata,
            "dataset_version": settings.provider_dataset_version,
            "location_key": location_key,
            "fetched_at": now,
        },
        "cache": {"status": "miss", "key": cache_key[:12]},
    }
    store.set_cache(
        cache_key,
        {
            "cache_key": cache_key,
            "algorithm_version": settings.algorithm_version,
            "dataset_version": settings.provider_dataset_version,
            "request_parameters": {
                "region": region_out,
                "start_year": req.start_year,
                "end_year": req.end_year,
                "baseline_start_year": req.baseline_start_year,
                "baseline_end_year": req.baseline_end_year,
            },
            "result": result,
            "created_at": now,
            "expires_at": now + settings.cache_ttl_seconds,
        },
    )
    # return a copy marked miss (stored copy keeps full key internally)
    return result
