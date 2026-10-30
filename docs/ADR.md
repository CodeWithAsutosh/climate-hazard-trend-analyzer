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

## ADR-4: Descriptive trend reporting, no causal claims
OLS slope on annual event counts plus early/late-half percentage change, with
explicit `insufficient_data` and undefined-change handling. A significance test is
reported alongside as separate evidence (ADR-7), never as an upgrade of the
wording: no causal language appears in API responses, UI, or docs, and a
significant Mann–Kendall result does not change that rule.

## ADR-5: No authentication by design
Public read-only analysis demo; adding login would be security theater. Abuse is
controlled via validation, body/region/period caps, per-IP rate limits, and caching.
If accounts or exports are added later, they need a reviewed auth/session design.

## ADR-6: Charts-first UI, map as a point-selection aid
Core workflow (form → charts → insights → quality) first. Charts carry the
analysis; a map is only a way to pick coordinates, not a way to imply spatial
coverage. Bounding boxes are accepted but analyzed via centroid with a visible
warning, rather than pretending full spatial aggregation exists. Leaflet was added
later for point mode only — see ADR-8.

## ADR-7: Mann–Kendall test with Sen's slope (bonus challenge)
The brief lists "apply trend detection techniques such as linear regression or the
Mann–Kendall test" as a bonus. Implemented as a pure-Python, dependency-free
two-sided test: S = Σ sign(xj − xi), variance with tie correction, continuity
correction, z from the normal CDF, α = 0.05, minimum n = 4, and an explicit caveat
that the normal approximation is rough for n < 8. Sen's slope is the median of
pairwise slopes **per calendar year**; because the series is filtered to
sufficient-coverage years, sample index is not year offset, so the year gap is
passed in explicitly (regression-tested against a hand-computed 0.5 events/year
fixture). Reported next to the OLS slope so the two can disagree visibly, which is
information rather than a defect. Hand-verified S/z/p fixtures cover the math.

## ADR-8: Leaflet map for point selection (bonus challenge)
The brief lists a map UI as a bonus. Leaflet + OpenStreetMap tiles are used only in
point mode: click to set coordinates, with manual entry still available. Rationale:
visual coordinate selection is the one thing a chart cannot do, and it avoids
implying that a bbox is spatially aggregated (it is still its centroid, per ADR-6).
Leaflet cannot run under jsdom (missing layout APIs), so it is contained in an error
boundary that degrades to manual entry; real map behaviour is verified by a
Chromium click-to-select E2E test instead of pretending a unit test covers it.
Attribution ("© OpenStreetMap contributors") is rendered, and deployers must allow
`tile.openstreetmap.org` in `img-src`.

## Bonus challenges — status
| Brief item | Status | Where |
|---|---|---|
| Map UI (Leaflet/Mapbox) | Shipped, point mode only | ADR-8, `frontend/src/components/MapPicker.tsx` |
| CSV export of insights | Shipped (annual table + summary metadata) | `frontend/src/utils/csv.ts` |
| PDF export | Not implemented — deferred, CSV covers the export need | README limitations |
| Linear regression / Mann–Kendall | Both shipped (OLS slope + Mann–Kendall/Sen's slope) | ADR-7, `backend/app/services/trends.py` |
