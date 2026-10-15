"""Hybrid store: MongoDB when configured, in-memory fallback otherwise.

Reason for fallback: local/test environments may not provide MongoDB.
Production should set MONGODB_URI (documented). Collections:
- daily_weather with unique (provider, location_key, date)
- analysis_cache with unique cache_key + TTL semantics enforced in code
  (plus a TTL index when MongoDB is used).
Thread-safe in-memory implementation guards concurrent cache misses.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.daily: dict[tuple, dict] = {}
        self.cache: dict[str, dict] = {}

    # daily weather
    def upsert_daily(self, docs: list[dict]) -> int:
        n = 0
        with self._lock:
            for d in docs:
                key = (d.get("provider"), d.get("location_key"), d.get("date"))
                if key not in self.daily:
                    n += 1
                self.daily[key] = d
        return n

    def count_daily(self) -> int:
        with self._lock:
            return len(self.daily)

    # analysis cache
    def get_cache(self, key: str, now: float) -> dict | None:
        with self._lock:
            doc = self.cache.get(key)
            if not doc:
                return None
            if doc.get("expires_at", 0) <= now:
                self.cache.pop(key, None)
                return None
            return dict(doc)

    def set_cache(self, key: str, doc: dict) -> None:
        with self._lock:
            # set-if-absent semantics for concurrent misses: first wins
            self.cache.setdefault(key, dict(doc))

    def stats(self) -> dict:
        with self._lock:
            return {"daily_records": len(self.daily), "cache_entries": len(self.cache)}


class MongoStore:
    def __init__(self, uri: str, db_name: str):
        from pymongo import MongoClient

        self.client: Any = MongoClient(uri, serverSelectionTimeoutMS=2000)
        self.db = self.client[db_name]
        self.daily = self.db["daily_weather"]
        self.cache = self.db["analysis_cache"]
        try:
            self.daily.create_index(
                [("provider", 1), ("location_key", 1), ("date", 1)], unique=True
            )
            self.cache.create_index([("cache_key", 1)], unique=True)
            self.cache.create_index([("expires_at", 1)], expireAfterSeconds=0)
        except Exception:
            pass

    def ping(self) -> bool:
        try:
            self.client.admin.command("ping")
            return True
        except Exception:
            return False

    def upsert_daily(self, docs: list[dict]) -> int:
        from pymongo import UpdateOne

        if not docs:
            return 0
        ops = [
            UpdateOne(
                {
                    "provider": d["provider"],
                    "location_key": d["location_key"],
                    "date": d["date"],
                },
                {"$set": d},
                upsert=True,
            )
            for d in docs
        ]
        try:
            res = self.daily.bulk_write(ops, ordered=False)
            return int(res.upserted_count + res.modified_count)
        except Exception:
            pass
        # Fallback for servers/drivers without bulk_write support: per-document
        # upserts. Slower, but preserves idempotency instead of losing writes.
        n = 0
        for d in docs:
            try:
                r = self.daily.update_one(
                    {
                        "provider": d["provider"],
                        "location_key": d["location_key"],
                        "date": d["date"],
                    },
                    {"$set": d},
                    upsert=True,
                )
                n += int(r.upserted_id is not None or r.modified_count > 0)
            except Exception:
                continue
        return n

    def get_cache(self, key: str, now: float) -> dict | None:
        try:
            doc = self.cache.find_one({"cache_key": key})
        except Exception:
            return None
        if not doc:
            return None
        try:
            if float(doc.get("expires_at", 0)) <= now:
                return None
        except (TypeError, ValueError):
            return None
        doc.pop("_id", None)
        return doc

    def set_cache(self, key: str, doc: dict) -> None:
        try:
            self.cache.update_one({"cache_key": key}, {"$setOnInsert": doc}, upsert=True)
        except Exception:
            pass


class HybridStore:
    """Exposes a uniform store interface; tracks backend kind."""

    def __init__(self, uri: str = "", db_name: str = "climatehazard"):
        self.kind = "memory"
        self.mem = MemoryStore()
        self.mongo: MongoStore | None = None
        self.mongo_error: str | None = None
        if uri:
            try:
                store = MongoStore(uri, db_name)
                if store.ping():
                    self.mongo = store
                    self.kind = "mongodb"
                else:
                    self.mongo_error = "ping failed"
            except Exception as e:
                self.mongo_error = str(e)[:200]

    def upsert_daily(self, docs: list[dict]) -> int:
        n = self.mem.upsert_daily(docs)
        if self.mongo is not None:
            try:
                self.mongo.upsert_daily(docs)
            except Exception:
                pass
        return n

    def get_cache(self, key: str, now: float | None = None) -> dict | None:
        ts = now if now is not None else time.time()
        hit = self.mem.get_cache(key, ts)
        if hit is not None:
            return hit
        if self.mongo is not None:
            try:
                doc = self.mongo.get_cache(key, ts)
            except Exception:
                return None
            if doc is not None:
                self.mem.set_cache(key, doc)
                return doc
        return None

    def set_cache(self, key: str, doc: dict) -> None:
        self.mem.set_cache(key, doc)
        if self.mongo is not None:
            try:
                self.mongo.set_cache(key, doc)
            except Exception:
                pass

    def stats(self) -> dict:
        s = self.mem.stats()
        s["backend"] = self.kind
        return s


_store: HybridStore | None = None
_store_lock = threading.Lock()


def get_store(uri: str = "", db_name: str = "climatehazard") -> HybridStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = HybridStore(uri, db_name)
        return _store


def reset_store() -> None:
    global _store
    with _store_lock:
        _store = None
