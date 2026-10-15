"""Provider client tests with controlled mocks (no network)."""

import httpx
import pytest

from app.services.weather_client import (
    ProviderError,
    build_archive_url,
    check_url_allowed,
    fetch_daily_max,
    parse_archive_payload,
)

BASE = "https://archive-api.open-meteo.com"


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=False)


def _ok_payload():
    return {
        "daily": {
            "time": ["2020-01-01", "2020-01-02"],
            "temperature_2m_max": [20.0, 21.0],
        },
        "daily_units": {"temperature_2m_max": "°C"},
    }


async def _fetch(client):
    return await fetch_daily_max(
        BASE,
        20.0,
        85.0,
        "2020-01-01",
        "2020-01-02",
        5.0,
        15.0,
        2_000_000,
        client=client,
    )


@pytest.mark.asyncio
async def test_success():
    async with _client(
        lambda r: httpx.Response(
            200, json=_ok_payload(), headers={"content-type": "application/json"}
        )
    ) as c:
        res = await _fetch(c)
    assert res.dates == ["2020-01-01", "2020-01-02"]
    assert res.tmax == [20.0, 21.0]


@pytest.mark.asyncio
async def test_empty_series_rejected():
    payload = {"daily": {"time": [], "temperature_2m_max": []}}
    async with _client(
        lambda r: httpx.Response(
            200, json=payload, headers={"content-type": "application/json"}
        )
    ) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.asyncio
async def test_malformed_json_blocked():
    async with _client(
        lambda r: httpx.Response(
            200, content=b"not json", headers={"content-type": "application/json"}
        )
    ) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.asyncio
async def test_unexpected_content_type_blocked():
    async with _client(
        lambda r: httpx.Response(200, content=b"<html/>", headers={"content-type": "text/html"})
    ) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 500, 502, 503])
@pytest.mark.asyncio
async def test_http_error_statuses(status):
    async with _client(
        lambda r: httpx.Response(status, json={}, headers={"content-type": "application/json"})
    ) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.asyncio
async def test_429_retry_then_success():
    calls = {"n": 0}

    def handler(r):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={}, headers={"content-type": "application/json"})
        return httpx.Response(
            200, json=_ok_payload(), headers={"content-type": "application/json"}
        )

    async with _client(handler) as c:
        res = await _fetch(c)
    assert res.dates[0] == "2020-01-01" and calls["n"] == 2


@pytest.mark.asyncio
async def test_repeated_transient_failures_give_up():
    async with _client(
        lambda r: httpx.Response(500, json={}, headers={"content-type": "application/json"})
    ) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.asyncio
async def test_timeout_enforced():
    def handler(r):
        raise httpx.ConnectTimeout("too slow")

    async with _client(handler) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.asyncio
async def test_redirect_blocked():
    async with _client(
        lambda r: httpx.Response(302, headers={"location": "https://evil.example/x"})
    ) as c:
        with pytest.raises(ProviderError):
            await _fetch(c)


@pytest.mark.asyncio
async def test_oversized_response_rejected():
    big = {"daily": {"time": ["2020-01-01"] * 100, "temperature_2m_max": [1.0] * 100}}
    async with _client(
        lambda r: httpx.Response(200, json=big, headers={"content-type": "application/json"})
    ) as c:
        with pytest.raises(ProviderError):
            await fetch_daily_max(
                BASE, 20.0, 85.0, "2020-01-01", "2020-01-02", 5.0, 15.0, 10, client=c
            )


def test_allowlist_blocks_unapproved_hosts():
    assert check_url_allowed(build_archive_url(BASE, 1, 1, "2020-01-01", "2020-01-02"), BASE)
    evil = "https://169.254.169.254/v1/archive?x=1"
    assert not check_url_allowed(evil, BASE)
    assert not check_url_allowed("http://archive-api.open-meteo.com/v1/archive?x=1", BASE)
    assert not check_url_allowed("https://evil.example/v1/archive", BASE)


def test_parse_rejects_envelope_variants():
    with pytest.raises(ProviderError):
        parse_archive_payload([1, 2, 3])
    with pytest.raises(ProviderError):
        parse_archive_payload({"daily": None})
    with pytest.raises(ProviderError):
        parse_archive_payload(
            {"daily": {"time": ["2020-01-01"], "temperature_2m_max": [1.0, 2.0]}}
        )
