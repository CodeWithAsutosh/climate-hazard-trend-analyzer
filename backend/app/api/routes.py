"""Versioned API routes with safe error handling."""

from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.config import get_settings
from app.repositories.store import get_store
from app.schemas.analysis import AnalysisRequest
from app.security.rate_limit import limiter
from app.services.analysis import run_analysis
from app.services.weather_client import ProviderError

router = APIRouter(prefix="/api/v1")


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    client = request.client
    return client.host if client else "unknown"


@router.get("/health")
async def health() -> dict:
    # Minimal disclosure: no env, paths, or credentials.
    return {"status": "ok", "service": "climate-hazard-trend-analyzer", "version": "1.0.0"}


@router.post("/analysis/heatwaves")
async def analyze_heatwaves(request: Request) -> JSONResponse:
    settings = get_settings()
    ip = _client_ip(request)
    ok, retry_after = limiter.check(f"analysis:{ip}", settings.rate_limit_analysis_per_min, 60)
    if not ok:
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "too many analysis requests; please retry shortly",
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
            headers={"Retry-After": str(retry_after)},
        )
    # Bounded body size
    body = await request.body()
    if len(body) > settings.max_request_bytes:
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "payload_too_large",
                    "message": "request body exceeds size limit",
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
        )
    ctype = request.headers.get("content-type", "")
    if "application/json" not in ctype:
        return JSONResponse(
            status_code=415,
            content={
                "error": {
                    "code": "unsupported_media_type",
                    "message": "content-type must be application/json",
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
        )
    try:
        payload = json.loads(body.decode("utf-8") if body else "null")
    except (ValueError, UnicodeDecodeError):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "malformed_json",
                    "message": "request body is not valid JSON",
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
        )
    # Block NoSQL-injection style operators before validation
    if isinstance(payload, dict):
        region = payload.get("region")
        if isinstance(region, dict) and any(str(k).startswith("$") for k in region.keys()):
            return JSONResponse(
                status_code=422,
                content={
                    "error": {
                        "code": "validation_error",
                        "message": "invalid region fields",
                        "request_id": getattr(request.state, "request_id", "n/a"),
                    }
                },
            )
    try:
        req = AnalysisRequest.model_validate(payload)
    except ValidationError as e:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "invalid request parameters",
                    "details": [
                        {"field": ".".join(map(str, err["loc"])), "message": err["msg"]}
                        for err in e.errors()[:10]
                    ],
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
        )
    store = get_store(settings.mongodb_uri, settings.mongodb_db)
    try:
        result = await run_analysis(req, settings, store)
        return JSONResponse(status_code=200, content=result)
    except ProviderError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "code": (
                        "upstream_error" if e.status_code in (502, 503) else "analysis_error"
                    ),
                    "message": str(e)[:300],
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
        )
    except Exception:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "unexpected internal failure",
                    "request_id": getattr(request.state, "request_id", "n/a"),
                }
            },
        )
