"""FastAPI application: correlation IDs, logging, CORS, security headers."""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings

log = logging.getLogger("climate-hazard")


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    app = FastAPI(
        title="Climate Hazard Trend Analyzer",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        debug=False,
    )
    app.include_router(router)

    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=False,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
            max_age=600,
        )

    @app.middleware("http")
    async def add_context(request: Request, call_next):  # type: ignore[no-untyped-def]
        rid = request.headers.get("x-request-id", uuid.uuid4().hex[:12])
        request.state.request_id = rid
        start = time.time()
        try:
            response = await call_next(request)
        except Exception:
            log.exception("unhandled request failure rid=%s", rid)
            return JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "internal_error",
                        "message": "unexpected internal failure",
                        "request_id": rid,
                    }
                },
            )
        elapsed = (time.time() - start) * 1000
        # structured log without secrets or bodies
        log.info(
            "rid=%s method=%s path=%s status=%s ms=%.1f",
            rid,
            request.method,
            request.url.path,
            getattr(response, "status_code", "?"),
            elapsed,
        )
        response.headers["X-Request-Id"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(Exception)
    async def safe_handler(request: Request, exc: Exception) -> JSONResponse:
        rid = getattr(request.state, "request_id", "n/a")
        log.exception("safe_handler rid=%s", rid)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "unexpected internal failure",
                    "request_id": rid,
                }
            },
        )

    return app


app = create_app()
