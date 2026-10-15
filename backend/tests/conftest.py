"""Shared fixtures: test settings + isolated stores."""

import pytest


@pytest.fixture(autouse=True)
def _test_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("MONGODB_URI", "")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("RATE_LIMIT_ANALYSIS_PER_MIN", "30")
    from app.config import reset_settings_cache

    reset_settings_cache()
    from app.repositories.store import reset_store
    from app.security.rate_limit import limiter

    reset_store()
    limiter.reset()
    yield
    reset_settings_cache()
    reset_store()
    limiter.reset()
