# Climate Hazard Trend Analyzer

Analyze historical **heatwave** trends for a selected region and period. The backend
retrieves daily maximum-temperature data from the Open-Meteo historical archive,
detects heatwave events with a documented, reproducible rule, and the React frontend
visualizes annual frequency, duration, intensity, and a descriptive trend summary —
with honest data-quality warnings throughout.

> No deployment has been performed in this workspace; there is no public demo URL.
> Run the stack locally with the steps below.
>
> Deployment targets (fill in after deploying):
>
> - Frontend: https://climate-hazard-trend-analyzer-steel.vercel.app/
> - Backend API: https://climate-hazard-trend-analyzer-33r3.onrender.com
>    (health: `https://climate-hazard-trend-analyzer-33r3.onrender.com/api/v1/health` —
>    verified live: cold analysis ~2.3 s miss, warm repeat hit, invalid input 422)

## Features

- Region selection: single lat/lon point **or** custom bounding box (≤ 5°×5°, ≤ 25 deg²,
   analyzed via its centroid — disclosed in UI and API). Point mode includes an
   interactive Leaflet map (click to set coordinates; tiles © OpenStreetMap contributors).
- Hazard selector with **Heatwave selected by default** (currently the only supported hazard).
- Custom analysis period (≤ 60 years, 1940–present) and configurable baseline
   (default 1991–2020, ≥ 5 years).
- Annual event counts + total heatwave days chart; duration/intensity chart; data-table
   alternatives for charts; trend summary tied to API results.
- **CSV export** of the annual table plus summary metadata (download button on results).
- **Mann–Kendall trend test** (two-sided, tie correction, α = 0.05) with **Sen's slope**,
   computed on the same sufficient-coverage annual series and shown in the insights.
- Coverage-by-year table, missing-data warnings, methodology disclosure, source attribution.
- Loading, empty, validation-error, rate-limit (429), upstream-error (502/503), and
   server-error states; duplicate-submission prevention; responsive + keyboard accessible.

## Architecture

```text
Browser (React 18 + TypeScript + Vite, Recharts)
  │  POST /api/v1/analysis/heatwaves (JSON)
  ▼
FastAPI backend (app/main.py → app/api/routes.py)
  ├─ Pydantic validation + per-IP sliding-window rate limiting
  ├─ services/analysis.py orchestration
  │    ├─ cache lookup (repositories/store.py: in-memory + MongoDB when configured)
  │    ├─ services/weather_client.py (allowlisted Open-Meteo HTTPS client)
  │    ├─ services/normalization.py (units, dedup, plausibility, gap preservation)
  │    ├─ services/heatwave.py (p95 threshold + ≥3-day run detection)
  │    └─ services/trends.py (annual aggregation, OLS slope, % change)
  └─ MongoDB persistence (daily_weather, analysis_cache) or memory fallback

```

Major components: see `backend/app/` and `frontend/src/`. Key decisions are recorded in
`docs/ADR.md`.

## Prerequisites

- Python 3.11+ (tested on 3.13), Node.js 20+ (tested on Node 25 / npm 11).
- MongoDB optional: without `MONGODB_URI` the backend uses a documented in-memory store
   (data does not survive restarts). Set `MONGODB_URI` for persistence.
- Internet access for the backend to reach `https://archive-api.open-meteo.com`
   (mocked in all automated tests; one manual live smoke test was performed).

## Local installation and startup

Backend:

```bash
cd backend
pip install -r requirements-dev.txt   # runtime + test/lint tooling
# (deployment installs requirements.txt — runtime only)
cp .env.example .env   # edit values; .env is git-ignored
uvicorn app.main:app --host 127.0.0.1 --port 8000

```

Frontend (new terminal):

```bash
cd frontend
npm install
npm run dev    # http://localhost:5173, /api proxied to localhost:8000

```

Production frontend build: `npm run build` (output in `frontend/dist/`).

## Environment variables

Backend (`backend/.env.example`, placeholders only):

| Name | Purpose | Default |
|---|---|---|
| `MONGODB_URI` | MongoDB connection string (empty = memory store) | `""` |
| `MONGODB_DB` | Database name | `climatehazard` |
| `CORS_ORIGINS` | Exact allowed origins, comma-separated | `http://localhost:5173` |
| `WEATHER_PROVIDER_BASE_URL` | Must be an allowlisted Open-Meteo host | `https://archive-api.open-meteo.com` |
| `WEATHER_CONNECT_TIMEOUT_S` / `WEATHER_READ_TIMEOUT_S` | Outbound timeouts | `5` / `15` |
| `WEATHER_MAX_RESPONSE_BYTES` | Upstream size cap | `2000000` |
| `RATE_LIMIT_ANALYSIS_PER_MIN` / `RATE_LIMIT_DEFAULT_PER_MIN` | Per-IP limits | `30` / `60` |
| `CACHE_TTL_SECONDS` | Analysis cache TTL | `86400` |
| `ALGORITHM_VERSION` / `PROVIDER_DATASET_VERSION` | Cache versioning | `v1` / `open-meteo-archive-v1` |
| `ENVIRONMENT` | `development`\|`test`\|`production` (disables docs in prod) | `development` |
| `MAX_REQUEST_BYTES` | Request body cap | `65536` |

Frontend (`frontend/.env.example`): `VITE_API_BASE_URL` (empty = same origin; public, not secret).

## Database setup and indexes

- Collections: `daily_weather` (unique `(provider, location_key, date)`),
   `analysis_cache` (unique `cache_key`, TTL on `expires_at`). Indexes are created on
   startup when MongoDB is configured (see `repositories/store.py`).
- Writes use bulk upserts with a per-document upsert fallback for drivers/servers
   without `bulk_write` support. The MongoDB code path is covered by mongomock-backed
   tests (  `backend/tests/test_mongo_store.py`); unique-index _enforcement_ against
   a live server is verified during deploy (inserting a duplicate must fail).
- Use a dedicated least-privilege user, TLS, and IP allowlisting in production.
- Without `MONGODB_URI`, the hybrid store keeps records in memory (documented fallback
   for development/test; not suitable for multi-instance production — see limitations).

## Data provider and attribution

- Source: __Open-Meteo Historical Weather Archive API__
   (`https://archive-api.open-meteo.com/v1/archive`, `daily=temperature_2m_max`,
   `temperature_unit=celsius`, `timezone=UTC`), coverage from 1940.
- Attribution shown in UI and API responses: “Weather data by Open-Meteo.com (CC-BY 4.0)”.
- Only the daily-maximum variable for the requested date span is fetched; responses are
   size-bounded and never returned raw to clients.

## Climate methodology and assumptions

- **Heatwave**: a maximal run of **≥ 3 consecutive valid days** with daily maximum
   temperature **strictly greater than** the region-specific **95th-percentile** threshold.
- **Baseline**: fixed period (default 1991–2020), configurable; threshold uses only valid
   baseline days (≥ 100 required, else HTTP 422).
- __Percentile method__: linear interpolation (numpy-`linear` equivalent), computed in
   `services/heatwave.py::percentile_linear`.
- **Seasonality**: threshold is **constant year-round** (non-seasonal). This is simple and
   disclosed, but can misclassify shoulder-season extremes — a documented limitation.
- **Missing data**: missing/invalid days and calendar gaps **break a run**; values are
   never interpolated and never treated as zero.
- **Event counting**: one event per maximal qualifying run (5 days = 1 event, not 3).
- **Year assignment**: year of the event **start** date (events crossing Jan 1 count in
   the starting year).
- **Duration**: number of days in the event. **Intensity**: per-day exceedance
   (`tmax − threshold`); event mean/max; annual mean of event means / max of event maxes.
- __Coverage__: a year needs ≥ 80% of expected daily values (`MIN_YEAR_COVERAGE`, a project
   assumption, not a scientific standard); < 90% raises an advisory warning.
- __Trend__: OLS slope on annual event counts (sufficient-coverage years only) plus
   late-half vs early-half mean percentage change `100·(late−early)/early`; undefined
   (null) when the early mean is zero. Requires ≥ 5 valid years and ≥ 70% valid-year
   fraction, else `insufficient_data`. A __Mann–Kendall test with Sen's slope__ runs on
   the same series (needs ≥ 4 points; normal-approximation caveat noted for n < 8).
   All trend output is __descriptive, not causal__.

## Missing-data and quality rules

- Provider payloads normalized to ISO dates and °C; Fahrenheit/Kelvin accepted where
   labeled; duplicates resolved deterministically (keep maximum); out-of-range values
   (< −90 °C or > 60 °C) marked invalid; suspicious-but-usable values flagged.
- Every response includes `quality.coverage_by_year`, `missing_days`, `warnings`, and
   normalization stats; bbox analyses carry a centroid-approximation warning.

## API endpoints and examples

`GET /api/v1/health` → `{"status":"ok","service":...,"version":"1.0.0"}` (no internals).

`POST /api/v1/analysis/heatwaves`:

```bash
curl -s http://localhost:8000/api/v1/analysis/heatwaves \
  -H 'Content-Type: application/json' -d '{
    "region": {"type": "point", "latitude": 28.6, "longitude": 77.2},
    "hazard": "heatwave",
    "start_year": 2015, "end_year": 2020,
    "baseline_start_year": 1991, "baseline_end_year": 2020
  }'

```

Response: `hazard, region, period, definition, threshold_c, baseline_observations,
annual[], summary{...}, quality{...}, source{...}, cache{status}`.
Status codes: `200` ok · `400` malformed JSON · `413` too large · `415` wrong content-type ·
`422` validation/insufficient baseline · `429` rate limited · `502/503` upstream failure ·
`500` generic + `request_id` (never stack traces or secrets).

## Caching and invalidation

- Cache key = SHA-256 of canonical validated inputs + `algorithm_version` +
   `provider_dataset_version` (server-generated; client keys never trusted).
- Raw daily docs and derived analyses cached separately, so algorithm bumps recompute
   without refetching. TTL 24 h (configurable). First writer wins on concurrent misses.
- Changing region, period, baseline, algorithm, or dataset version yields a different key.

## Test commands

```bash
# Backend (108 unit/integration/security + 3 perf = 111 tests)
cd backend && pytest
pytest --cov=app --cov-report=term-missing   # needs pytest-cov (not installed)
ruff check app tests && ruff format --check app tests
mypy app

# Frontend (16 Vitest tests)
cd frontend && npm run lint && npm run typecheck && npm run test && npm run build

# End-to-end (8 Playwright tests: 4 scenarios × desktop + mobile)
cd frontend && npx playwright install chromium && npx playwright test

```

Live-provider tests are opt-in/manual only (one smoke test performed; see test report).

## Security controls and limitations

Implemented and tested: strict Pydantic bounds (coords, years, bbox size, body size);
NaN/±∞ and bool rejection; `$`-operator rejection; exact CORS origins (no credentials);
per-IP rate limits + `Retry-After`; allowlisted HTTPS-only provider host; redirects
blocked (SSRF); connect/read timeouts; bounded retries with backoff; response size caps;
server-side cache keys; safe error envelopes with correlation IDs; structured logging
without secrets/bodies; security headers (`nosniff`, `frame DENY`, referrer policy);
docs disabled in production; no secrets in frontend bundle; React-escaped rendering only.

Limitations (honest): single-instance in-memory rate limiter/store unless MongoDB/shared
infra is configured; no authentication (public read-only demo by design); CSP/HSTS/TLS
must be set at the hosting layer; residual devDependency audit findings documented in
`docs/TEST_REPORT.md`. This app is __not claimed to be completely secure__.

## Deployment instructions

1. Provision managed MongoDB; create least-privilege app user; restrict network access.
2. Deploy backend (uvicorn/Gunicorn) with secrets __only__ in host env/secret manager;
   set `ENVIRONMENT=production`, exact `CORS_ORIGINS`, tuned rate limits/timeouts.
3. Serve `frontend/dist/` over HTTPS; set `VITE_API_BASE_URL` at build time; configure
   CSP, HSTS, and other headers at the host/CDN. Allow `tile.openstreetmap.org` in
   `img-src` (and `connect-src` if tiles are fetched via XHR) for the Leaflet map.
4. Verify on deploy: health, one real analysis, cache hit, invalid input, rate limit,
   and log redaction. See the deployment checklist in the implementation plan.

## Known limitations and future improvements

- No live MongoDB cluster in this workspace: the MongoDB code path is verified via
   mongomock-backed tests; unique-index enforcement and Atlas wiring remain manual
   deploy-time checks.
- Bbox = centroid grid cell (disclosed); map covers point mode only; no named-city
   geocoding yet.
- Non-seasonal threshold; Mann–Kendall uses the normal approximation (rough for n < 8,
   disclosed); descriptive trends only.
- No background jobs: very long periods are bounded (60 y) but slow on cold cache.
- E2E mocks the API (no live weather dependence) except the real-browser map test;
   CI workflow written but not executed on GitHub (no repo/remote configured here).
- With more time: geocoding, seasonal (day-of-year) thresholds, PDF export,
   Redis/shared rate limiting, and hosted deployment.

## AI tools used

Built with **Muse Spark (via OpenCode)** as the implementation assistant: scaffolding,
backend services, frontend components, and the full test suite were drafted with AI help
and then executed, debugged, and verified locally (all test/lint/build/security commands
were actually run; failures — a bool-coercion bug, jsdom gaps, broken pip state, audit
findings — were investigated and fixed, with regressions covered by tests).
Follow-up additions built the same way: Mann–Kendall/Sen's slope (verified against
hand-computed S/z/p fixtures), mongomock-backed MongoDB path tests (which exposed and
fixed a bulk-write compatibility gap via a per-document fallback), CSV export, and the
Leaflet map (jsdom incompatibility contained with an error boundary; verified by a
real-browser click-to-select E2E test).
