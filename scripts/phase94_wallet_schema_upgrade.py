#!/usr/bin/env python3
"""Phase 94 — Idempotent wallet schema upgrade. Safe to run multiple times."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.neon_service import fast_query, write_query

MIGRATIONS = [
    # chain_wallets — already exists, add missing columns only
    "ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS pending_cents INT DEFAULT 0",
    "ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS earnings_cents INT DEFAULT 0",
    "ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS withdrawable_cents INT DEFAULT 0",
    "ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD'",
    "ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",

    # chain_wallet_transactions — already exists, add missing columns
    "ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS fee_cents INT DEFAULT 0",
    "ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS net_amount_cents INT",
    "ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS idempotency_key TEXT",
    "ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS related_content_type TEXT",
    "ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS related_content_id TEXT",
    "ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS metadata JSONB",

    # chain_creator_earnings
    """
    CREATE TABLE IF NOT EXISTS chain_creator_earnings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        creator_id UUID NOT NULL,
        source_type TEXT NOT NULL,
        source_id TEXT,
        gross_cents INT NOT NULL DEFAULT 0,
        fee_cents INT NOT NULL DEFAULT 0,
        net_cents INT NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'pending',
        transaction_id TEXT,
        available_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # chain_payout_requests — may exist, add columns
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS wallet_id UUID",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD'",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS payout_account_masked TEXT",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS payout_account_encrypted TEXT",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS idempotency_key TEXT",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS payout_reference TEXT",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS admin_id UUID",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS admin_notes TEXT",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS requested_at TIMESTAMPTZ DEFAULT now()",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS approved_at TIMESTAMPTZ",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS rejected_at TIMESTAMPTZ",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ",
    "ALTER TABLE chain_payout_requests ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now()",

    # chain_wallet_holds
    """
    CREATE TABLE IF NOT EXISTS chain_wallet_holds (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        wallet_id UUID,
        profile_id UUID NOT NULL,
        amount_cents INT NOT NULL DEFAULT 0,
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        related_type TEXT,
        related_id TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        released_at TIMESTAMPTZ
    )
    """,

    # chain_payment_audit_logs
    """
    CREATE TABLE IF NOT EXISTS chain_payment_audit_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        actor_id UUID,
        target_profile_id UUID,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id TEXT,
        old_status TEXT,
        new_status TEXT,
        amount_cents INT,
        ip_address TEXT,
        user_agent TEXT,
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # chain_fraud_flags
    """
    CREATE TABLE IF NOT EXISTS chain_fraud_flags (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID NOT NULL,
        flag_type TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'medium',
        reason TEXT,
        status TEXT NOT NULL DEFAULT 'open',
        related_type TEXT,
        related_id TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        reviewed_at TIMESTAMPTZ,
        reviewed_by UUID
    )
    """,
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_earnings_creator_status ON chain_creator_earnings (creator_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_payout_status_created ON chain_payout_requests (status, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_holds_wallet_status ON chain_wallet_holds (wallet_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_holds_profile_status ON chain_wallet_holds (profile_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON chain_payment_audit_logs (actor_id)",
    "CREATE INDEX IF NOT EXISTS idx_audit_log_target ON chain_payment_audit_logs (target_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_fraud_flags_user ON chain_fraud_flags (profile_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_fraud_flags_type ON chain_fraud_flags (flag_type, status)",
    "CREATE INDEX IF NOT EXISTS idx_payout_unique_ref ON chain_payout_requests (payout_reference) WHERE payout_reference IS NOT NULL",
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_payout_idempotency ON chain_payout_requests (idempotency_key) WHERE idempotency_key IS NOT NULL",
]

def run():
    count = 0
    for sql in MIGRATIONS:
        try:
            write_query(sql)
            count += 1
        except Exception as e:
            print(f"  [SKIP] {e}")
    for sql in INDEXES:
        try:
            write_query(sql)
            count += 1
        except Exception as e:
            print(f"  [SKIP] {e}")
    print(f"Migration complete: {count} statements executed (idempotent)")
    return count

if __name__ == "__main__":
    c1 = run()
    c2 = run()
    assert c1 == c2, "Not idempotent!"
    print("Idempotent: OK")
