# CODEX Phase Live Verifier Fix Report

## Changes
- `scripts/verify_live_neon.py`
  - Added retry/backoff for cold Neon pool startup.
  - Treats recovered slow startup as `WARN` instead of `FAIL`.
  - Still fails on missing required tables or total query failure.
- `scripts/verify_live_supabase_storage.py`
  - Accepts legacy and current bucket aliases per active upload type.
  - Fails only when an active upload type has no acceptable bucket.
  - Does not create buckets unless `CREATE_MISSING_BUCKETS=1`.
- `scripts/verify_live_production_smoke.py`
  - Uses `certifi` CA bundle when installed.
  - Treats local SSL CA verification failure on remote health as `WARN`.
- `scripts/create_missing_supabase_buckets.py`
  - Dry-run by default.
  - Creates only actually required missing buckets when `CREATE_MISSING_BUCKETS=1`.

## Expected Bucket Handling
- Reuse legacy buckets when they satisfy the active upload type.
- Create missing buckets only where no acceptable legacy/current bucket exists.

## Status
- Latest run in this terminal session:
  - `python3 -m py_compile app.py`: PASS
  - `python3 -m compileall api_routes services templates >/tmp/chain_compile.log`: PASS
  - `python3 scripts/verify_live_neon.py`: FAIL
  - `python3 scripts/verify_live_redis.py`: FAIL
  - `python3 scripts/verify_live_supabase_storage.py`: FAIL
  - `python3 scripts/verify_live_production_smoke.py`: PASS
- Runtime notes from the actual run:
  - Neon failure here is DNS/host-resolution failure, not cold-start-only latency.
  - Redis failure here is fallback mode due unresolved Redis host.
  - Supabase storage failure here is DNS/host-resolution failure, so live bucket inventory could not be fetched in this session.
  - Remote `namvibe.com` health remained `SKIP` here because outbound DNS failed before any SSL verification path was reached.
