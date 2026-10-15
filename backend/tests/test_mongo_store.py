"""MongoDB store tests against mongomock (isolated, no server needed).

These verify the real MongoStore code path: unique compound indexes,
upsert idempotency, cache set-if-absent, expiry, and HybridStore selection.
A live-cluster test remains manual (see README deployment steps).
"""

import time

import mongomock
import pytest

from app.repositories.store import HybridStore, MongoStore


@pytest.fixture()
def mongo_store(monkeypatch):
    monkeypatch.setattr("pymongo.MongoClient", mongomock.MongoClient)
    return MongoStore("mongodb://test:27017", "testdb")


def _doc(day: str, t: float = 20.0) -> dict:
    return {
        "provider": "open-meteo",
        "location_key": "20.0000,85.0000",
        "date": day,
        "tmax_c": t,
        "valid": True,
    }


def test_upsert_daily_inserts_and_dedupes(mongo_store):
    docs = [_doc("2020-01-01"), _doc("2020-01-02")]
    assert mongo_store.upsert_daily(docs) == 2
    assert mongo_store.daily.count_documents({}) == 2
    # re-upsert same docs: no duplicates created
    mongo_store.upsert_daily(docs)
    assert mongo_store.daily.count_documents({}) == 2


def test_upsert_daily_updates_changed_values(mongo_store):
    mongo_store.upsert_daily([_doc("2020-01-01", 20.0)])
    mongo_store.upsert_daily([_doc("2020-01-01", 25.0)])
    assert mongo_store.daily.find_one({"date": "2020-01-01"})["tmax_c"] == 25.0


def test_unique_compound_index_metadata(mongo_store):
    # NOTE: mongomock does not enforce unique indexes server-side, so this
    # verifies the index definition our code creates. Enforcement against a
    # live server is covered by the Atlas check in the README deploy steps.
    idx = {ix["name"]: ix for ix in mongo_store.daily.list_indexes()}
    compound = [
        ix
        for ix in idx.values()
        if list(dict(ix["key"]).items()) == [("provider", 1), ("location_key", 1), ("date", 1)]
    ]
    assert len(compound) == 1
    assert compound[0]["unique"] is True


def test_cache_roundtrip_and_expiry(mongo_store):
    now = time.time()
    mongo_store.set_cache("k1", {"cache_key": "k1", "result": {"a": 1}, "expires_at": now + 60})
    hit = mongo_store.get_cache("k1", now)
    assert hit is not None and hit["result"] == {"a": 1}
    assert "_id" not in hit
    mongo_store.set_cache("k2", {"cache_key": "k2", "result": {}, "expires_at": now - 1})
    assert mongo_store.get_cache("k2", now) is None
    assert mongo_store.get_cache("missing", now) is None


def test_cache_first_writer_wins(mongo_store):
    now = time.time()
    mongo_store.set_cache("k", {"cache_key": "k", "result": {"w": 1}, "expires_at": now + 60})
    mongo_store.set_cache("k", {"cache_key": "k", "result": {"w": 2}, "expires_at": now + 60})
    assert mongo_store.get_cache("k", now)["result"] == {"w": 1}


def test_hybrid_selects_mongodb_when_ping_succeeds(monkeypatch):
    monkeypatch.setattr("pymongo.MongoClient", mongomock.MongoClient)
    s = HybridStore("mongodb://test:27017", "testdb")
    assert s.kind == "mongodb"
    assert s.mongo is not None
    n = s.upsert_daily([_doc("2020-01-01")])
    assert n == 1
    assert s.mongo.daily.count_documents({}) == 1


def test_hybrid_falls_back_when_unreachable():
    s = HybridStore("mongodb://127.0.0.1:1/?serverSelectionTimeoutMS=200", "testdb")
    assert s.kind == "memory"
    assert s.mongo_error is not None
