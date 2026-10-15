# Test Report (executed 2026-10-13; counts re-verified 2026-10-15, Windows, Python 3.13, Node 25)

## Summary

| Layer | Command | Passed | Failed | Skipped | Not run |
|---|---|---|---|---|---|
| Backend unit/integration/security/perf | `cd backend && pytest` | 125 | 0 | 0 | 0 |
| Backend lint | `ruff check app tests` | pass | — | — | — |
| Backend format | `ruff format --check app tests` | pass | — | — | — |
| Backend types | `mypy app` | pass | — | — | — |
| Frontend unit/component | `cd frontend && npm run test` | 20 | 0 | 0 | 0 |
| Frontend lint | `npm run lint` | pass | — | — | — |
| Frontend typecheck | `npm run typecheck` | pass | — | — | — |
| Frontend build | `npm run build` | pass | — | — | — |
| E2E (desktop + mobile) | `npx playwright test` | 10 | 0 | 0 | 0 |
| Coverage (`--cov`) | — | — | — | — | not run (pytest-cov not installed) |
| CI workflow | `.github/workflows/ci.yml` | — | — | — | not run (no GitHub remote configured) |
| Live deployment | prod smoke (Vercel→Render→Open-Meteo) | pass (1) | 0 | 0 | 0 |

Backend breakdown (125): heatwave 17 · normalization 12 · trends 9 · mann-kendall 7 ·
validation 28 · weather-client 18 · API/security 15 · cache 9 · mongo-store 7 ·
performance 3 · conftest fixtures.
(Counts verified via `pytest --collect-only`; include parametrized cases.)
Frontend breakdown (20): validation 8 · AnalyzerPage 8 · CSV 1 · MapPicker 3.
E2E breakdown (10): 5 scenarios × desktop + mobile viewports.

## Regressions found and fixed during development

1. Bool accepted as coordinate (`True` → 1.0): added explicit bool rejection +
   regression test (`test_malformed_coordinates_rejected[True]`).
2. Broken pip state after upgrade (stale `~astapi` dir, missing RECORD): cleared
   manually, force-repaired, suite re-run green.
3. jsdom missing `ResizeObserver` (recharts) and missing render cleanup: stub + cleanup
   in `tests/setup.ts`.
4. Playwright strict-mode violation (attribution in footer and panel): scoped assertion.
5. Warm-cache perf test used an insufficient fixture (never hit cache): enlarged to a
   cache-engaging series with hit/miss assertions.
6. mongomock lacks `bulk_write` parity and unique-index enforcement: production code
   gained a per-document upsert fallback (resilience, not test-gaming); the unique
   test asserts index metadata, with live enforcement a deploy-time check.
7. Leaflet crashes in jsdom (missing layout APIs): contained with an error boundary
   that keeps manual coordinate entry usable; real map behavior verified by a
   Chromium click-to-select E2E test.

No test was disabled, weakened, or deleted to obtain a green build.

## Security scans

- `pip-audit --requirement requirements.txt`: **0 vulnerabilities** (after upgrading
  fastapi 0.116→0.143, starlette 0.47→1.7, pymongo→4.18.2, anyio→4.14.2, pytest→9.0.3,
  pytest-asyncio→1.4.0; suite re-run green after each bump).
- Full-environment `pip-audit`: 61 findings in unrelated system packages
  (torch, authlib, mcp, …) — outside this project's dependency tree.
- `npm audit`: 13 remaining, all in dev-only tooling (vitest/vite/esbuild advisories
  affecting the local dev server/test runner, never shipped in `dist/`). Reduced from
  18 via safe upgrades; major vitest v4 migration deferred as disproportionate risk.
- Secret scan: no `.env` files in repo; `.env.example` files contain placeholders only;
  no credentials/secrets found in `frontend/dist` assets.

## Performance measurements (actual, local machine)

- Live provider fetch (2 y daily, Open-Meteo): ~3.4 s (network-bound).
- Full cold analysis Delhi 2015–2020 (30 y fetched incl. baseline): **~2.0 s** end to end.
- Warm-cache repeat: **~0.008 s** (`cache.status: hit`).
- 22,000-day normalization + detection: < 1 s (test bound 5 s each).
- Bounded concurrency (10 threads, cache-miss race): single winner, no duplicates.
- Load testing with k6/Locust was not performed (no tooling provisioned; upstream
  must not be load-tested). Do not claim scalability beyond these measurements.

## Manual verification performed

- Live MongoDB persistence: primed Mumbai 2000–2009 analysis (miss, key
  `300cdab9434f`), restarted the Render service, repeated the identical request →
  `hit` on the same key. Memory-only caching cannot survive a restart.

- Real end-to-end analysis via HTTP (Delhi 2015–2020): threshold 41.3 °C, 11 events,
  decreasing descriptive trend −42.86% with caveats; cache miss→hit confirmed.
- Real provider smoke test (2019–2020 sample): 731 days, °C, HTTP 200.
- Invalid-input, 429, 502, and 500 paths exercised through HTTP tests with
  no-stack-trace / no-secret assertions.
