#!/usr/bin/env python3
"""Phase 95 — Idempotent moderation schema upgrade. Safe to run multiple times."""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from services.neon_service import fast_query, write_query

MIGRATIONS = [
    # chain_restrictions — persistent restriction tracking
    """
    CREATE TABLE IF NOT EXISTS chain_restrictions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID NOT NULL,
        restricted_by_profile_id UUID,
        restriction_type TEXT DEFAULT 'temporary',
        reason TEXT,
        status TEXT DEFAULT 'active',
        duration_minutes INTEGER DEFAULT 1440,
        expires_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # chain_content_flags — content moderation flags
    """
    CREATE TABLE IF NOT EXISTS chain_content_flags (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID NOT NULL,
        content_type TEXT NOT NULL,
        content_id UUID NOT NULL,
        flag_type TEXT NOT NULL,
        severity TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'active',
        flagged_by_profile_id UUID,
        reason TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        resolved_at TIMESTAMPTZ
    )
    """,

    # chain_account_risk — account risk scoring
    """
    CREATE TABLE IF NOT EXISTS chain_account_risk (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID UNIQUE NOT NULL,
        risk_level TEXT DEFAULT 'low',
        risk_score INTEGER DEFAULT 0,
        new_account BOOLEAN DEFAULT true,
        no_profile BOOLEAN DEFAULT false,
        mass_action_count INTEGER DEFAULT 0,
        report_count INTEGER DEFAULT 0,
        restriction_count INTEGER DEFAULT 0,
        signals JSONB DEFAULT '{}'::jsonb,
        updated_at TIMESTAMPTZ DEFAULT now(),
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # chain_appeals — appeal system
    """
    CREATE TABLE IF NOT EXISTS chain_appeals (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id UUID NOT NULL,
        appeal_type TEXT NOT NULL,
        target_id TEXT,
        reason TEXT,
        details TEXT,
        status TEXT DEFAULT 'pending',
        reviewed_by_profile_id UUID,
        resolution_note TEXT,
        created_at TIMESTAMPTZ DEFAULT now(),
        resolved_at TIMESTAMPTZ
    )
    """,

    # chain_moderation_logs — audit trail
    """
    CREATE TABLE IF NOT EXISTS chain_moderation_logs (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        actor_profile_id UUID,
        target_profile_id UUID,
        action TEXT NOT NULL,
        entity_type TEXT,
        entity_id TEXT,
        reason TEXT,
        details JSONB DEFAULT '{}'::jsonb,
        ip_address TEXT,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,

    # Add missing columns to existing tables (idempotent, safe)
    "ALTER TABLE chain_restrictions ADD COLUMN IF NOT EXISTS duration_minutes INTEGER DEFAULT 1440",
]

INDEXES = [
    # chain_restrictions indexes
    "CREATE INDEX IF NOT EXISTS idx_restrictions_profile ON chain_restrictions (profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_restrictions_status ON chain_restrictions (status)",
    "CREATE INDEX IF NOT EXISTS idx_restrictions_expires ON chain_restrictions (expires_at)",

    # chain_content_flags indexes
    "CREATE INDEX IF NOT EXISTS idx_content_flags_profile ON chain_content_flags (profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_content_flags_content ON chain_content_flags (content_type, content_id)",
    "CREATE INDEX IF NOT EXISTS idx_content_flags_status ON chain_content_flags (status)",
    "CREATE INDEX IF NOT EXISTS idx_content_flags_flag_type ON chain_content_flags (flag_type)",

    # chain_account_risk indexes
    "CREATE INDEX IF NOT EXISTS idx_account_risk_profile ON chain_account_risk (profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_account_risk_level ON chain_account_risk (risk_level)",

    # chain_appeals indexes
    "CREATE INDEX IF NOT EXISTS idx_appeals_profile ON chain_appeals (profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_appeals_status ON chain_appeals (status)",
    "CREATE INDEX IF NOT EXISTS idx_appeals_type ON chain_appeals (appeal_type)",

    # chain_moderation_logs indexes
    "CREATE INDEX IF NOT EXISTS idx_mod_logs_actor ON chain_moderation_logs (actor_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_mod_logs_target ON chain_moderation_logs (target_profile_id)",
    "CREATE INDEX IF NOT EXISTS idx_mod_logs_action ON chain_moderation_logs (action)",
    "CREATE INDEX IF NOT EXISTS idx_mod_logs_created ON chain_moderation_logs (created_at)",
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
