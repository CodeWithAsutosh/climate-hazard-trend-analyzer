"""Input validation tests for every documented rejection class."""

import datetime

import pytest
from pydantic import ValidationError

from app.schemas.analysis import AnalysisRequest

CURRENT = datetime.date.today().year

VALID = {
    "region": {"type": "point", "latitude": 20.0, "longitude": 85.0},
    "hazard": "heatwave",
    "start_year": 1990,
    "end_year": 2020,
    "baseline_start_year": 1991,
    "baseline_end_year": 2020,
}

if CURRENT < 2020:  # pragma: no cover - time travel guard
    VALID = dict(
        VALID,
        start_year=1990,
        end_year=CURRENT,
        baseline_start_year=1990,
        baseline_end_year=CURRENT,
    )


def req(**over):
    base = dict(VALID)
    base.update(over)
    return base


def test_valid_point_accepted():
    assert AnalysisRequest.model_validate(req()).start_year == req()["start_year"]


def test_valid_bbox_accepted():
    r = req(
        region={
            "type": "bbox",
            "min_lat": 19.0,
            "max_lat": 21.0,
            "min_lon": 84.0,
            "max_lon": 86.0,
        }
    )
    assert AnalysisRequest.model_validate(r).region.type == "bbox"


@pytest.mark.parametrize("lat", [-90.1, 90.1, -1000.0, 1000.0])
def test_latitude_out_of_range(lat):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            req(region={"type": "point", "latitude": lat, "longitude": 0.0})
        )


@pytest.mark.parametrize("lon", [-180.1, 180.1, -999.0, 999.0])
def test_longitude_out_of_range(lon):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            req(region={"type": "point", "latitude": 0.0, "longitude": lon})
        )


@pytest.mark.parametrize("bad", ["abc", None, [1], {"$gt": 5}, True])
def test_malformed_coordinates_rejected(bad):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            req(region={"type": "point", "latitude": bad, "longitude": 0.0})
        )


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_coordinates_rejected(bad):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            req(region={"type": "point", "latitude": bad, "longitude": 0.0})
        )


def test_missing_region_rejected():
    d = req()
    del d["region"]
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(d)


def test_wrong_types_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(req(start_year="1990x"))


def test_reversed_years_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(req(start_year=2020, end_year=1990))


def test_reversed_baseline_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(req(baseline_start_year=2020, baseline_end_year=1991))


def test_unsupported_hazard_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(req(hazard="flood"))


def test_excessively_long_period_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            req(
                start_year=1940,
                end_year=1940 + 60,
                baseline_start_year=1991,
                baseline_end_year=2020,
            )
        )


def test_oversized_bbox_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            req(
                region={
                    "type": "bbox",
                    "min_lat": 0.0,
                    "max_lat": 10.0,
                    "min_lon": 0.0,
                    "max_lon": 10.0,
                }
            )
        )


def test_short_baseline_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(req(baseline_start_year=2019, baseline_end_year=2020))


def test_future_year_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(req(start_year=CURRENT + 1, end_year=CURRENT + 1))


def test_extra_fields_rejected():
    d = req()
    d["region"] = dict(d["region"], hacker=True)
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(d)
