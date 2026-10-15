"""Application configuration with strict environment validation."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_uri: str = Field(default="", description="MongoDB connection string")
    mongodb_db: str = Field(default="climatehazard")
    cors_origins: str = Field(default="http://localhost:5173")
    weather_provider_base_url: str = Field(default="https://archive-api.open-meteo.com")
    weather_connect_timeout_s: float = Field(default=5.0, ge=1.0, le=30.0)
    weather_read_timeout_s: float = Field(default=15.0, ge=5.0, le=60.0)
    weather_max_response_bytes: int = Field(default=2_000_000, ge=10_000, le=20_000_000)
    rate_limit_analysis_per_min: int = Field(default=30, ge=1, le=600)
    rate_limit_default_per_min: int = Field(default=60, ge=1, le=2000)
    cache_ttl_seconds: int = Field(default=86400, ge=60, le=2_592_000)
    algorithm_version: str = Field(default="v1")
    provider_dataset_version: str = Field(default="open-meteo-archive-v1")
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    max_request_bytes: int = Field(default=65536, ge=1024, le=1_000_000)

    @field_validator("weather_provider_base_url")
    @classmethod
    def _validate_provider_base(cls, v: str) -> str:
        allowed = {
            "https://archive-api.open-meteo.com",
            "https://api.open-meteo.com",
        }
        normalized = v.rstrip("/")
        if normalized not in allowed:
            raise ValueError("weather provider base URL must be an allowlisted Open-Meteo host")
        return normalized

    @field_validator("environment")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        if v not in {"development", "test", "production"}:
            raise ValueError("environment must be development|test|production")
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def use_mongo(self) -> bool:
        return bool(self.mongodb_uri)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
