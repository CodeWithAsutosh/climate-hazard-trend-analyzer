"""API integration tests through HTTP (mocked provider, isolated store)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.analysis as analysis_mod
from app.config import get_settings
from app.main import create_app
from app.services.weather_client import ProviderError, ProviderResult


def _provider_result(n_years: int = 6, hot: bool = True) -> ProviderResult:
    from datetime import date, timedelta

    start = date(2000, 1, 1)
    days = 365 * n_years + 2
    dates, tmax = [], []
    for i in range(days):
        d = start + timedelta(days=i)
        dates.append(d.isoformat())
        # baseline-friendly: warm summers produce heatwaves against p95
        tmax.append(38.0 if (hot and d.month in (5, 6, 7) and d.day % 4 != 0) else 22.0)
    return ProviderResult(
        dates=dates, tmax=tmax, unit="celsius", source_metadata={"provider": "open-meteo"}
    )


@pytest.fixture()
def client(monkeypatch):
    async def fake_fetch(*a, **k):
        return _provider_result()

    monkeypatch.setattr(analysis_mod, "fetch_daily_max", fake_fetch)
    app = create_app()
    return TestClient(app, raise_server_exceptions=False)


def _payload(**over):
    base = {
        "region": {"type": "point", "latitude": 20.0, "longitude": 85.0},
        "hazard": "heatwave",
        "start_year": 2000,
        "end_year": 2005,
        "baseline_start_year": 2000,
        "baseline_end_year": 2005,
    }
    base.update(over)
    return base


def test_health_minimal_disclosure(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.text.lower()
    assert "mongodb" not in body and "secret" not in body and "traceback" not in body


def test_valid_request_schema_and_metadata(client):
    r = client.post("/api/v1/analysis/heatwaves", json=_payload())
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    assert data["hazard"] == "heatwave"
    assert data["cache"]["status"] == "miss"
    assert isinstance(data["threshold_c"], int | float)
    assert len(data["annual"]) == 6
    assert data["summary"]["method"]
    assert data["definition"]["minimum_consecutive_days"] == 3
    assert "quality" in data and "source" in data


def test_cache_hit_on_repeat(client):
    assert (
        client.post("/api/v1/analysis/heatwaves", json=_payload()).json()["cache"]["status"]
        == "miss"
    )
    second = client.post("/api/v1/analysis/heatwaves", json=_payload()).json()
    assert second["cache"]["status"] == "hit"


def test_cache_key_changes_with_params(client):
    first = client.post("/api/v1/analysis/heatwaves", json=_payload()).json()
    altered = _payload(end_year=2004)
    second = client.post("/api/v1/analysis/heatwaves", json=altered).json()
    assert second["cache"]["status"] == "miss"
    assert second["period"] != first["period"]


def test_invalid_region_rejected(client):
    r = client.post(
        "/api/v1/analysis/heatwaves",
        json=_payload(region={"type": "point", "latitude": 99.0, "longitude": 0.0}),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_reversed_years_rejected(client):
    r = client.post("/api/v1/analysis/heatwaves", json=_payload(start_year=2005, end_year=2000))
    assert r.status_code == 422


def test_unknown_hazard_rejected(client):
    p = _payload()
    p["hazard"] = "volcano"
    assert client.post("/api/v1/analysis/heatwaves", json=p).status_code == 422


def test_malformed_json_400(client):
    r = client.post(
        "/api/v1/analysis/heatwaves",
        content=b"{bad json",
        headers={"content-type": "application/json"},
    )
    assert r.status_code == 400


def test_unsupported_content_type_415(client):
    r = client.post(
        "/api/v1/analysis/heatwaves", content="x=1", headers={"content-type": "text/plain"}
    )
    assert r.status_code == 415


def test_oversized_request_413(client):
    big = {
        "region": {"type": "point", "latitude": 1.0, "longitude": 1.0},
        "hazard": "heatwave",
        "start_year": 2000,
        "end_year": 2005,
        "baseline_start_year": 2000,
        "baseline_end_year": 2005,
        "pad": "x" * 70000,
    }
    r = client.post("/api/v1/analysis/heatwaves", json=big)
    assert r.status_code == 413


def test_nosql_injection_blocked(client):
    r = client.post(
        "/api/v1/analysis/heatwaves",
        json=_payload(region={"type": "point", "$gt": 1, "latitude": 1.0, "longitude": 1.0}),
    )
    assert r.status_code in (400, 422)


def test_rate_limit_429(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_analysis_per_min", 2)
    # limiter is per-IP; TestClient uses same IP
    assert client.post("/api/v1/analysis/heatwaves", json=_payload()).status_code == 200
    assert client.post("/api/v1/analysis/heatwaves", json=_payload()).status_code == 200
    r = client.post("/api/v1/analysis/heatwaves", json=_payload())
    assert r.status_code == 429
    assert "Retry-After" in r.headers


def test_upstream_failure_safe_error(client, monkeypatch):
    async def boom(*a, **k):
        raise ProviderError("provider down", 502, False)

    monkeypatch.setattr(analysis_mod, "fetch_daily_max", boom)
    r = client.post("/api/v1/analysis/heatwaves", json=_payload())
    assert r.status_code == 502
    body = r.text.lower()
    assert "traceback" not in body and "mongodb" not in body
    assert r.json()["error"]["code"] == "upstream_error"


def test_unexpected_exception_no_leak(client, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("super secret db password=xyz")

    monkeypatch.setattr(analysis_mod, "fetch_daily_max", boom)
    r = client.post("/api/v1/analysis/heatwaves", json=_payload())
    assert r.status_code == 500
    assert "xyz" not in r.text and "traceback" not in r.text.lower()


def test_security_headers_present(client):
    r = client.get("/api/v1/health")
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert "X-Request-Id" in r.headers
