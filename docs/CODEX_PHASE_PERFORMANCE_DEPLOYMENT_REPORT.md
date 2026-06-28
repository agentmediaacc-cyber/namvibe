# CODEX Phase Performance + Deployment Report

## Confirmed Fixes
- `services/feed_ranking_service.py`
  - Batched creator verification badge lookup for ranked feed/reel items.
  - Removes per-item badge queries from homepage and reel ranking paths.
- `scripts/benchmark_production_routes.py`
  - Added local runtime benchmark for `/`, `/reels/`, `/search`, `/healthz`, `/health/db`, `/health/redis`, and `/health/supabase`.
  - Includes non-secret env-var presence checks and deployment file checks.

## Deployment Notes
- `Dockerfile` and `render.yaml` are present.
- No secrets are printed by the benchmark script.

## Status
- Compile
  - `python3 -m py_compile app.py`: PASS
  - `python3 -m compileall api_routes services templates >/tmp/chain_compile.log`: PASS
- Live verifiers
  - `python3 scripts/verify_live_neon.py`: FAIL
  - `python3 scripts/verify_live_redis.py`: FAIL
  - `python3 scripts/verify_live_supabase_storage.py`: FAIL
  - `python3 scripts/verify_live_production_smoke.py`: PASS
- Benchmark
  - `/`: avg `55.69ms`, min `5.7ms`, max `155.57ms`, status `200`
  - `/reels/`: avg `9.47ms`, min `3.24ms`, max `21.86ms`, status `200`
  - `/search`: avg `10.69ms`, min `2.59ms`, max `25.97ms`, status `200`
  - `/healthz`: avg `2.69ms`, min `2.1ms`, max `3.75ms`, status `200`
  - `/health/db`: avg `1.57ms`, min `1.36ms`, max `1.78ms`, status `503`
  - `/health/redis`: avg `4.2ms`, min `1.45ms`, max `9.08ms`, status `503`
  - `/health/supabase`: avg `17.67ms`, min `1.42ms`, max `50.06ms`, status `200`
- Runtime notes
  - Remaining live verifier failures in this session are DNS/host-resolution failures for Neon, Redis, and Supabase, not confirmed application regressions.
  - `Dockerfile` and `render.yaml` are present and detected by the benchmark script.
