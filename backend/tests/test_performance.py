"""Performance/reliability bounds (mocked provider; generous CI-safe limits)."""

from __future__ import annotations

import time
from datetime import date, timedelta

from fastapi.testclient import TestClient

import app.services.analysis as analysis_mod
from app.main import create_app
from app.services.heatwave import detect_heatwaves
from app.services.normalization import normalize_daily_series
from app.services.weather_client import ProviderResult


def _big_series(days: int = 22_000):
    start = date(1960, 1, 1)
    dates = [(start + timedelta(days=i)).isoformat() for i in range(days)]
    tmax = [38.0 if (i % 30 < 5) else 22.0 for i in range(days)]
    return dates, tmax


def test_normalization_and_detection_max_size_fast():
    dates, tmax = _big_series()
    t0 = time.perf_counter()
    recs, _ = normalize_daily_series(dates, tmax, "celsius")
    t1 = time.perf_counter()
    evs = detect_heatwaves(recs, 30.0)
    t2 = time.perf_counter()
    assert len(recs) == 22_000
    assert len(evs) > 0
    assert (t1 - t0) < 5.0, f"normalization too slow: {t1 - t0:.2f}s"
    assert (t2 - t1) < 5.0, f"detection too slow: {t2 - t1:.2f}s"


def test_warm_cache_latency_bound():
    from datetime import date as _date

    base = _date(2000, 1, 1)
    dates = [(base + timedelta(days=i)).isoformat() for i in range(2200)]
    tmax = [38.0 if (i % 30 < 5) else 22.0 for i in range(2200)]

    async def fake_fetch(*a, **k):
        return ProviderResult(
            dates=dates,
            tmax=tmax,
            unit="celsius",
            source_metadata={"provider": "open-meteo"},
        )

    # minimal monkeypatch without pytest fixture machinery
    orig = analysis_mod.fetch_daily_max
    analysis_mod.fetch_daily_max = fake_fetch  # type: ignore[assignment]
    try:
        client = TestClient(create_app(), raise_server_exceptions=False)
        body = {
            "region": {"type": "point", "latitude": 20.0, "longitude": 85.0},
            "hazard": "heatwave",
            "start_year": 2000,
            "end_year": 2005,
            "baseline_start_year": 2000,
            "baseline_end_year": 2005,
        }
        # prime cache with a bigger mocked series via direct run is overkill;
        # warm path measured on validation-only repeat after first miss
        first = client.post("/api/v1/analysis/heatwaves", json=body)
        assert first.status_code == 200, first.text[:300]
        assert first.json()["cache"]["status"] == "miss"
        t0 = time.perf_counter()
        r = client.post("/api/v1/analysis/heatwaves", json=body)
        dt = time.perf_counter() - t0
        assert r.status_code == 200
        assert r.json()["cache"]["status"] == "hit"
        assert dt < 2.0, f"warm request too slow: {dt:.2f}s"
    finally:
        analysis_mod.fetch_daily_max = orig


def test_empty_records_instant():
    assert detect_heatwaves([], 30.0) == []
