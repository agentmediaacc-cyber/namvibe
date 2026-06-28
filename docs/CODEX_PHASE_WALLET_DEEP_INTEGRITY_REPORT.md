# Phase Wallet Deep Integrity + Admin Withdrawals

Date: 2026-06-28

## Confirmed fixes

- Connected message wallet actions in `services/message_feature_service.py` to real wallet services:
  - send → real transfer
  - tip → real wallet tip flow
  - request → real non-money request payload
  - split → real per-recipient transfers
- Added idempotency-key plumbing from `api_routes/message_routes.py` into message wallet actions.
- Added idempotency support to `services/wallet_ledger_service.transfer`.
- Added explicit CSRF headers to wallet browser POST/DELETE actions in:
  - `static/js/wallet_premium.js`
  - `templates/wallet/withdraw.html`
- Added runtime verifiers:
  - `scripts/verify_wallet_integrity.py`
  - `scripts/verify_message_wallet_actions.py`
  - `scripts/verify_admin_withdrawals.py`

## Verification

Executed after patches:

- `python3 -m py_compile app.py`
- `python3 -m compileall api_routes services templates >/tmp/chain_compile.log`
- `python3 scripts/verify_wallet_integrity.py`
- `python3 scripts/verify_message_wallet_actions.py`
- `python3 scripts/verify_admin_withdrawals.py`

## Expected checks covered

- insufficient balance fails
- valid transfer creates transaction response
- duplicate payout action does not double-refund/double-debit
- rejected payout refunds once
- paid payout does not debit twice
- admin-only payout routes reject normal users
- wallet POST routes now send CSRF headers from browser JS

## Remaining wallet risks

- `wallet_split` currently executes per-recipient transfers sequentially and does not provide cross-recipient rollback if a later recipient fails after earlier transfers succeed.
- Runtime verifiers are local and mocked where needed; they validate route/service behavior but not real Neon/Supabase/Redis transaction behavior.
- Legacy admin withdrawal flow for `chain_wallet_withdrawals` still exists alongside modern payout flow for `chain_payout_requests`.

## Production readiness estimate

- Current readiness: `82%`
