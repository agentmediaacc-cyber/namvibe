# CODEX Phase Atomic Split + Live Validation Report

## Scope
- Wallet split atomicity and idempotency
- Live Neon, Redis, Supabase, and production smoke verification

## Confirmed Fixes
- `services/message_feature_service.py`
  - `wallet_split` now validates all recipients, duplicate recipients, total amount, and sender membership before any transfer executes.
  - DB-backed split execution now uses one Neon transaction path and returns all-or-nothing results.
  - Local fallback split execution now compensates on failure and prevents partial-success responses.
  - Split-level idempotency now prevents replay of completed split requests.
- `scripts/verify_wallet_integrity.py`
  - Added checks for split duplicate-recipient rejection, rollback on partial failure, and split idempotency.

## Live Validation Scripts
- `scripts/verify_live_neon.py`
- `scripts/verify_live_redis.py`
- `scripts/verify_live_supabase_storage.py`
- `scripts/verify_live_production_smoke.py`

## Verification Notes
- Live dependency scripts do not print secrets.
- Remote `namvibe.com` health is treated as optional and reports skip when the environment blocks outbound access.
- Protected-route checks require redirect or `401/403`, not `200`.

## Status
- Wallet split local integrity verifiers pass.
- Local production smoke verifier passes.
- Live dependency probes currently fail in this environment because Neon, Redis, and Supabase host resolution is unavailable.
- Remote `https://namvibe.com/healthz` is skipped when outbound DNS is unavailable.
