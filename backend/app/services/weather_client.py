"""Secure Open-Meteo archive client with allowlist, timeouts, bounded retries."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass

import httpx

ALLOWED_HOSTS = {"archive-api.open-meteo.com", "api.open-meteo.com"}
ARCHIVE_PATH = "/v1/archive"
MAX_ATTEMPTS = 3
BASE_BACKOFF_S = 0.5


class ProviderError(Exception):
    def __init__(self, message: str, status_code: int = 502, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass
class ProviderResult:
    dates: list[str]
    tmax: list[object]
    unit: str
    source_metadata: dict


def build_archive_url(base_url: str, lat: float, lon: float, start: str, end: str) -> str:
    from urllib.parse import urlencode

    params = urlencode(
        {
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "start_date": start,
            "end_date": end,
            "daily": "temperature_2m_max",
            "timezone": "UTC",
            "temperature_unit": "celsius",
        }
    )
    return f"{base_url.rstrip('/')}{ARCHIVE_PATH}?{params}"


def check_url_allowed(url: str, allowed_base: str) -> bool:
    try:
        from urllib.parse import urlparse

        want = urlparse(allowed_base)
        got = urlparse(url)
        if got.scheme != "https":
            return False
        if got.hostname not in ALLOWED_HOSTS:
            return False
        if want.hostname != got.hostname:
            # allow either of the two allowlisted hosts as configured base
            if got.hostname not in ALLOWED_HOSTS:
                return False
        if not got.path.startswith(ARCHIVE_PATH):
            return False
        return True
    except Exception:
        return False


async def fetch_daily_max(
    base_url: str,
    latitude: float,
    longitude: float,
    start_date: str,
    end_date: str,
    connect_timeout: float,
    read_timeout: float,
    max_bytes: int,
    client: httpx.AsyncClient | None = None,
) -> ProviderResult:
    url = build_archive_url(base_url, latitude, longitude, start_date, end_date)
    if not check_url_allowed(url, base_url):
        raise ProviderError("provider URL failed allowlist check", 500, False)
    owns_client = client is None
    if owns_client:
        timeout = httpx.Timeout(
            connect=connect_timeout, read=read_timeout, write=read_timeout, pool=5.0
        )
        client = httpx.AsyncClient(timeout=timeout, follow_redirects=False, max_redirects=0)
    assert client is not None
    try:
        last_exc: Exception | None = None
        for attempt in range(MAX_ATTEMPTS):
            try:
                resp = await client.get(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "climate-hazard-analyzer/1.0",
                    },
                )
                if resp.status_code in (301, 302, 303, 307, 308):
                    # Block redirects: never follow to unapproved destinations.
                    raise ProviderError("provider redirect blocked", 502, False)
                if resp.status_code == 429:
                    raise ProviderError("provider rate limit exceeded", 502, True)
                if 500 <= resp.status_code <= 599:
                    raise ProviderError(f"provider server error {resp.status_code}", 502, True)
                if resp.status_code == 400:
                    raise ProviderError("provider rejected request", 502, False)
                if resp.status_code in (401, 403, 404):
                    raise ProviderError(f"provider error {resp.status_code}", 502, False)
                if resp.status_code != 200:
                    raise ProviderError(
                        f"provider unexpected status {resp.status_code}", 502, False
                    )
                ctype = resp.headers.get("content-type", "")
                if "application/json" not in ctype:
                    raise ProviderError("provider unexpected content type", 502, False)
                # bound response size
                content = resp.content
                if len(content) > max_bytes:
                    raise ProviderError("provider response too large", 502, False)
                try:
                    payload = resp.json()
                except Exception:
                    raise ProviderError("provider malformed JSON", 502, False) from None
                return parse_archive_payload(payload, url)
            except ProviderError as e:
                if e.retryable and attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(BASE_BACKOFF_S * (2**attempt) + random.uniform(0, 0.2))
                    continue
                raise
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_exc = e
                if attempt < MAX_ATTEMPTS - 1:
                    await asyncio.sleep(BASE_BACKOFF_S * (2**attempt) + random.uniform(0, 0.2))
                    continue
                raise ProviderError("provider request timed out", 502, False) from e
            except httpx.HTTPError as e:
                raise ProviderError("provider connection failed", 502, False) from e
        raise ProviderError("provider request failed", 502, False) from last_exc
    finally:
        if owns_client:
            await client.aclose()


def parse_archive_payload(payload: object, url: str = "") -> ProviderResult:
    if not isinstance(payload, dict):
        raise ProviderError("provider malformed response envelope", 502, False)
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise ProviderError("provider missing daily data", 502, False)
    dates = daily.get("time")
    tmax = daily.get("temperature_2m_max")
    if not isinstance(dates, list) or not isinstance(tmax, list):
        raise ProviderError("provider malformed daily series", 502, False)
    if len(dates) != len(tmax):
        raise ProviderError("provider mismatched series lengths", 502, False)
    if len(dates) == 0:
        raise ProviderError("provider returned empty series", 502, False)
    if len(dates) > 30_000:
        raise ProviderError("provider response too large", 502, False)
    units = payload.get("daily_units", {})
    unit = "celsius"
    if isinstance(units, dict) and isinstance(units.get("temperature_2m_max"), str):
        raw_u: str = units["temperature_2m_max"]
        if "°F" in raw_u or "(°F)" in raw_u or "F" == raw_u.strip("°() "):
            unit = "fahrenheit"
    meta = {
        "provider": "open-meteo",
        "endpoint": "archive",
        "attribution": "Weather data by Open-Meteo.com (CC-BY 4.0)",
        "units": unit,
    }
    return ProviderResult(
        dates=[str(d) for d in dates], tmax=list(tmax), unit=unit, source_metadata=meta
    )
