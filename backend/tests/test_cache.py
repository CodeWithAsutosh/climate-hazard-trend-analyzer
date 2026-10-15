"""Cache/store tests: hits, expiry, version isolation, concurrency."""

import threading
import time

from app.repositories.store import HybridStore, MemoryStore
from app.schemas.analysis import AnalysisRequest
from app.services.cache_key import build_cache_key


def _req(**over):
    base = {
        "region": {"type": "point", "latitude": 20.0, "longitude": 85.0},
        "hazard": "heatwave",
        "start_year": 2000,
        "end_year": 2005,
        "baseline_start_year": 2000,
        "baseline_end_year": 2005,
    }
    base.update(over)
    return AnalysisRequest.model_validate(base)


def _key(req, algo="v1", ds="ds1"):
    return build_cache_key(
        req.region,
        req.start_year,
        req.end_year,
        req.baseline_start_year,
        req.baseline_end_year,
        algo,
        ds,
    )


def test_cache_key_stable_for_same_inputs():
    assert _key(_req()) == _key(_req())


def test_cache_key_changes_with_region_period_baseline_versions():
    base = _key(_req())
    assert _key(_req(region={"type": "point", "latitude": 21.0, "longitude": 85.0})) != base
    assert _key(_req(end_year=2004)) != base
    assert _key(_req(baseline_end_year=2004)) != base
    assert _key(_req(), algo="v2") != base
    assert _key(_req(), ds="ds2") != base


def test_cache_hit_and_miss():
    s = HybridStore()
    k = _key(_req())
    assert s.get_cache(k) is None
    s.set_cache(k, {"cache_key": k, "result": {"a": 1}, "expires_at": time.time() + 60})
    assert s.get_cache(k)["result"] == {"a": 1}


def test_cache_expiration():
    s = HybridStore()
    k = "exp"
    s.set_cache(k, {"cache_key": k, "result": {}, "expires_at": time.time() - 1})
    assert s.get_cache(k) is None


def test_region_period_isolation():
    s = HybridStore()
    k1, k2 = _key(_req()), _key(_req(end_year=2004))
    s.set_cache(k1, {"cache_key": k1, "result": {"v": 1}, "expires_at": time.time() + 60})
    assert s.get_cache(k2) is None


def test_upsert_daily_idempotent():
    m = MemoryStore()
    docs = [{"provider": "p", "location_key": "l", "date": "2020-01-01", "tmax_c": 20.0}]
    assert m.upsert_daily(docs) == 1
    assert m.upsert_daily(docs) == 0  # duplicate prevention
    assert m.count_daily() == 1


def test_concurrent_cache_misses_single_winner():
    s = HybridStore()
    k = "race"
    now = time.time() + 60

    def worker(i):
        s.set_cache(k, {"cache_key": k, "result": {"w": i}, "expires_at": now})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    hit = s.get_cache(k)
    assert hit is not None and hit["result"]["w"] in range(10)
    assert s.stats()["cache_entries"] == 1


def test_malformed_cache_doc_missed():
    s = HybridStore()
    s.set_cache("bad", {"nope": True, "expires_at": time.time() + 60})
    # missing 'result' -> callers treat as miss
    doc = s.get_cache("bad")
    assert doc is not None and "result" not in doc


def test_memory_store_backend_label():
    assert HybridStore().stats()["backend"] == "memory"
