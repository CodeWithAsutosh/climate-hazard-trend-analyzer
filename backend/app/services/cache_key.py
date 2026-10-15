"""Canonical cache keys: sha256 of validated inputs + versions."""

from __future__ import annotations

import hashlib
import json


def canonical_region(region) -> dict:
    if getattr(region, "type", None) == "point":
        return {
            "type": "point",
            "latitude": round(float(region.latitude), 4),
            "longitude": round(float(region.longitude), 4),
        }
    return {
        "type": "bbox",
        "min_lat": round(float(region.min_lat), 4),
        "max_lat": round(float(region.max_lat), 4),
        "min_lon": round(float(region.min_lon), 4),
        "max_lon": round(float(region.max_lon), 4),
    }


def build_cache_key(
    region,
    start_year: int,
    end_year: int,
    baseline_start: int,
    baseline_end: int,
    algorithm_version: str,
    dataset_version: str,
) -> str:
    canonical = {
        "region": canonical_region(region),
        "start_year": int(start_year),
        "end_year": int(end_year),
        "baseline_start_year": int(baseline_start),
        "baseline_end_year": int(baseline_end),
        "hazard": "heatwave",
        "algorithm_version": algorithm_version,
        "dataset_version": dataset_version,
    }
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
