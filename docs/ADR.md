# Architecture Decision Record

## ADR-1: One provider — Open-Meteo archive
Single daily-max-temperature source behind a narrow client interface. Rationale:
no key required, generous free historical coverage (1940+), CC-BY 4.0 with clear
attribution. Multi-provider failover deferred as unnecessary complexity/risk.

## ADR-2: MongoDB with documented in-memory fallback
MongoDB is the persistence layer (unique compound index on daily records; unique
key + TTL on analysis cache). Because disposable local MongoDB was unavailable in
this workspace, a thread-safe in-memory `HybridStore` backs development/test while
preserving the same upsert/get/set semantics and key/version isolation, all covered
by tests. Production must set `MONGODB_URI` (plus shared rate limiting) for
multi-instance correctness.

## ADR-3: Fixed baseline, constant year-round p95 threshold
Threshold = 95th percentile (linear interpolation) of valid baseline daily maxima,
default baseline 1991–2020, strict `>` comparison, missing days break runs, event
year = start year. A fixed baseline keeps historical comparisons stable; the
non-seasonal threshold is simpler but disclosed as potentially misclassifying
shoulder-season extremes. No silent interpolation, ever.

## ADR-4: Descriptive trends only
OLS slope + early/late-half percentage change, with explicit `insufficient_data`
and undefined-change handling. No significance tests, no causal language anywhere
in API responses, UI, or docs.

## ADR-5: No authentication by design
Public read-only analysis demo; adding login would be security theater. Abuse is
controlled via validation, body/region/period caps, per-IP rate limits, and caching.
If accounts or exports are added later, they need a reviewed auth/session design.

## ADR-6: Recharts over a map-first UI
Core workflow (form → charts → insights → quality) first; no map library shipped.
Bounding boxes are accepted but analyzed via centroid with a visible warning, rather
than pretending full spatial aggregation exists.
