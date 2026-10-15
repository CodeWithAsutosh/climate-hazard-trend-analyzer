"""Strict Pydantic request/response schemas for heatwave analysis."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

MIN_YEAR = 1940
MAX_ANALYSIS_SPAN_YEARS = 60
MIN_BASELINE_SPAN_YEARS = 5
MAX_BBOX_SPAN_DEG = 5.0
MAX_BBOX_AREA_DEG2 = 25.0
SUPPORTED_HAZARDS = {"heatwave"}


def _reject_nonfinite(v: float, name: str) -> float:
    if isinstance(v, bool):
        raise ValueError(f"{name} must be a number")
    if not isinstance(v, int | float):
        raise ValueError(f"{name} must be a number")
    f = float(v)
    if not math.isfinite(f):
        raise ValueError(f"{name} must be finite")
    return f


class PointRegion(BaseModel):
    model_config = {"extra": "forbid"}
    type: Literal["point"] = "point"
    latitude: float
    longitude: float

    @field_validator("latitude", mode="before")
    @classmethod
    def _lat(cls, v: object) -> float:
        if isinstance(v, bool):
            raise ValueError("latitude must be a number")
        f = _reject_nonfinite(v, "latitude")  # type: ignore[arg-type]
        if f < -90 or f > 90:
            raise ValueError("latitude must be between -90 and 90")
        return f

    @field_validator("longitude", mode="before")
    @classmethod
    def _lon(cls, v: object) -> float:
        if isinstance(v, bool):
            raise ValueError("longitude must be a number")
        f = _reject_nonfinite(v, "longitude")  # type: ignore[arg-type]
        if f < -180 or f > 180:
            raise ValueError("longitude must be between -180 and 180")
        return f


class BBoxRegion(BaseModel):
    model_config = {"extra": "forbid"}
    type: Literal["bbox"] = "bbox"
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float

    @model_validator(mode="after")
    def _check(self) -> BBoxRegion:
        for name in ("min_lat", "max_lat", "min_lon", "max_lon"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int | float):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(float(v)):
                raise ValueError(f"{name} must be finite")
        if not (-90 <= self.min_lat <= 90 and -90 <= self.max_lat <= 90):
            raise ValueError("bbox latitudes must be within -90..90")
        if not (-180 <= self.min_lon <= 180 and -180 <= self.max_lon <= 180):
            raise ValueError("bbox longitudes must be within -180..180")
        if self.min_lat >= self.max_lat:
            raise ValueError("min_lat must be < max_lat")
        if self.min_lon >= self.max_lon:
            raise ValueError("min_lon must be < max_lon")
        if (self.max_lat - self.min_lat) > MAX_BBOX_SPAN_DEG:
            raise ValueError(f"bbox latitude span must be <= {MAX_BBOX_SPAN_DEG} degrees")
        if (self.max_lon - self.min_lon) > MAX_BBOX_SPAN_DEG:
            raise ValueError(f"bbox longitude span must be <= {MAX_BBOX_SPAN_DEG} degrees")
        area = (self.max_lat - self.min_lat) * (self.max_lon - self.min_lon)
        if area > MAX_BBOX_AREA_DEG2:
            raise ValueError(f"bbox area must be <= {MAX_BBOX_AREA_DEG2} deg^2")
        return self

    @property
    def centroid(self) -> tuple[float, float]:
        return (
            round((self.min_lat + self.max_lat) / 2, 4),
            round((self.min_lon + self.max_lon) / 2, 4),
        )


Region = PointRegion | BBoxRegion


class AnalysisRequest(BaseModel):
    model_config = {"extra": "forbid"}
    region: PointRegion | BBoxRegion = Field(discriminator="type")
    hazard: Literal["heatwave"] = "heatwave"
    start_year: int = Field(ge=MIN_YEAR, le=2100)
    end_year: int = Field(ge=MIN_YEAR, le=2100)
    baseline_start_year: int = Field(default=1991, ge=MIN_YEAR, le=2100)
    baseline_end_year: int = Field(default=2020, ge=MIN_YEAR, le=2100)

    @model_validator(mode="after")
    def _check_years(self) -> AnalysisRequest:
        import datetime

        current_year = datetime.date.today().year
        for f in ("start_year", "end_year", "baseline_start_year", "baseline_end_year"):
            y = getattr(self, f)
            if y > current_year:
                raise ValueError(f"{f} must be <= {current_year}")
        if self.start_year > self.end_year:
            raise ValueError("start_year must be <= end_year")
        if self.baseline_start_year > self.baseline_end_year:
            raise ValueError("baseline_start_year must be <= baseline_end_year")
        if (self.end_year - self.start_year + 1) > MAX_ANALYSIS_SPAN_YEARS:
            raise ValueError(f"analysis period must be <= {MAX_ANALYSIS_SPAN_YEARS} years")
        if (self.baseline_end_year - self.baseline_start_year + 1) < MIN_BASELINE_SPAN_YEARS:
            raise ValueError(f"baseline period must span >= {MIN_BASELINE_SPAN_YEARS} years")
        return self


class AnnualResult(BaseModel):
    year: int
    event_count: int
    total_heatwave_days: int
    mean_duration_days: float | None
    max_duration_days: int | None
    mean_intensity_c: float | None
    max_intensity_c: float | None
    coverage_fraction: float
    sufficient_coverage: bool


class TrendSummary(BaseModel):
    direction: Literal["increasing", "decreasing", "no_clear_trend", "insufficient_data"]
    slope_events_per_year: float | None
    method: str
    early_period: dict | None = None
    late_period: dict | None = None
    change_percent: float | None = None
    change_percent_calculable: bool = True
    caveats: list[str] = Field(default_factory=list)
    mann_kendall: dict | None = None


class AnalysisResponse(BaseModel):
    hazard: str = "heatwave"
    region: dict
    period: dict
    definition: dict
    threshold_c: float | None
    annual: list[AnnualResult]
    summary: TrendSummary
    quality: dict
    source: dict
    cache: dict
