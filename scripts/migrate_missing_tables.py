#!/usr/bin/env python3
"""Create all missing DB tables referenced in code but not yet in Neon."""

import os, sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["FLASK_ENV"] = "development"
os.environ["CHAIN_FAST_LOCAL"] = "1"
os.environ["ALLOW_LOCAL_AUTH_FALLBACK"] = "true"

from services.neon_service import write_query, fast_query
from services.logging_service import log_info, log_error

# Tables with known DDL from ensure_content_schema()
KNOWN_DDL = {
    "chain_media_processing_jobs": """
        CREATE TABLE IF NOT EXISTS chain_media_processing_jobs (
            id text PRIMARY KEY,
            entity_type text NOT NULL,
            entity_id text NOT NULL,
            profile_id text NOT NULL,
            input_url text NOT NULL,
            output_url text,
            status text NOT NULL DEFAULT 'pending',
            target_resolution text DEFAULT '720p',
            error_message text,
            created_at text NOT NULL,
            updated_at text NOT NULL
        )
    """,
    "chain_story_media_items": """
        CREATE TABLE IF NOT EXISTS chain_story_media_items (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            story_id uuid REFERENCES chain_status_posts(id) ON DELETE CASCADE,
            media_type text DEFAULT 'photo',
            media_url text,
            thumbnail_url text,
            width integer DEFAULT 1080,
            height integer DEFAULT 1920,
            duration_seconds numeric DEFAULT 0,
            position integer DEFAULT 0,
            created_at timestamptz DEFAULT now()
        )
    """,
}

# Auto-generated DDL for all other missing tables
# Column types inferred from naming conventions
AUTO_DDL = {}

AUTO_DDL["chain_account_risk"] = """
    CREATE TABLE IF NOT EXISTS chain_account_risk (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        risk_score integer DEFAULT 0,
        risk_factors jsonb DEFAULT '{}',
        last_assessed_at timestamptz DEFAULT now(),
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_account_security"] = """
    CREATE TABLE IF NOT EXISTS chain_account_security (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL UNIQUE,
        password_set boolean DEFAULT false,
        recovery_enabled boolean DEFAULT false,
        two_factor_enabled boolean DEFAULT false,
        last_reviewed_at timestamptz,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_activity_events"] = """
    CREATE TABLE IF NOT EXISTS chain_activity_events (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text,
        event_type text,
        entity_type text,
        entity_id text,
        metadata jsonb DEFAULT '{}',
        ip_address text,
        user_agent text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_ai_chat_sessions"] = """
    CREATE TABLE IF NOT EXISTS chain_ai_chat_sessions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text,
        session_data jsonb DEFAULT '{}',
        status text DEFAULT 'active',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_ai_feedback"] = """
    CREATE TABLE IF NOT EXISTS chain_ai_feedback (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text,
        feedback_type text,
        rating integer,
        comment text,
        metadata jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_ai_moderation_log"] = """
    CREATE TABLE IF NOT EXISTS chain_ai_moderation_log (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        content_id text,
        content_type text,
        decision text,
        confidence numeric DEFAULT 0,
        reason text,
        reviewed_by text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_ai_suggestions"] = """
    CREATE TABLE IF NOT EXISTS chain_ai_suggestions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text,
        suggestion_type text,
        suggestion_data jsonb DEFAULT '{}',
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_appeals"] = """
    CREATE TABLE IF NOT EXISTS chain_appeals (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        target_id text,
        appeal_type text,
        reason text,
        details text,
        status text DEFAULT 'pending',
        resolution text,
        resolved_by text,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_bookings"] = """
    CREATE TABLE IF NOT EXISTS chain_bookings (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text,
        service_id text,
        provider_id text,
        status text DEFAULT 'pending',
        booking_data jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_callkit_payloads"] = """
    CREATE TABLE IF NOT EXISTS chain_callkit_payloads (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        call_id text,
        call_type text,
        caller_name text,
        push_payload jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_campaigns"] = """
    CREATE TABLE IF NOT EXISTS chain_campaigns (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        name text,
        description text,
        status text DEFAULT 'draft',
        audience text,
        budget integer DEFAULT 0,
        reach integer DEFAULT 0,
        clicks integer DEFAULT 0,
        engagement integer DEFAULT 0,
        views integer DEFAULT 0,
        start_date timestamptz,
        end_date timestamptz,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_content_flags"] = """
    CREATE TABLE IF NOT EXISTS chain_content_flags (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        content_id text,
        content_type text,
        flag_type text,
        flagged_by text,
        reason text,
        severity text DEFAULT 'low',
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_creator_levels"] = """
    CREATE TABLE IF NOT EXISTS chain_creator_levels (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL UNIQUE,
        level integer DEFAULT 1,
        experience_points bigint DEFAULT 0,
        title text,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_creator_post_visibility"] = """
    CREATE TABLE IF NOT EXISTS chain_creator_post_visibility (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        post_id text,
        visibility_rule jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_creator_stats"] = """
    CREATE TABLE IF NOT EXISTS chain_creator_stats (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL UNIQUE,
        total_earnings bigint DEFAULT 0,
        total_followers integer DEFAULT 0,
        total_views bigint DEFAULT 0,
        total_likes bigint DEFAULT 0,
        total_comments bigint DEFAULT 0,
        total_shares bigint DEFAULT 0,
        total_saves bigint DEFAULT 0,
        engagement_rate numeric DEFAULT 0,
        stats_data jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_creator_tools"] = """
    CREATE TABLE IF NOT EXISTS chain_creator_tools (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL UNIQUE,
        studio_enabled boolean DEFAULT false,
        monetization_enabled boolean DEFAULT false,
        creator_notes text,
        featured_links jsonb DEFAULT '[]',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_creator_verification_requests"] = """
    CREATE TABLE IF NOT EXISTS chain_creator_verification_requests (
        id text PRIMARY KEY,
        creator_profile_id text NOT NULL,
        verification_type text,
        submitted_data jsonb DEFAULT '{}',
        status text DEFAULT 'pending',
        reviewed_by text,
        review_notes text,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_data_requests"] = """
    CREATE TABLE IF NOT EXISTS chain_data_requests (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        data_export boolean DEFAULT false,
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_encrypted_sessions"] = """
    CREATE TABLE IF NOT EXISTS chain_encrypted_sessions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        peer_profile_id text,
        thread_id text,
        session_type text,
        session_key_id text,
        session_data jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_fraud_events"] = """
    CREATE TABLE IF NOT EXISTS chain_fraud_events (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        event_type text,
        severity text DEFAULT 'low',
        score numeric DEFAULT 0,
        metadata jsonb DEFAULT '{}',
        payout_request_id text,
        wallet_transaction_id text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_group_encryption_keys"] = """
    CREATE TABLE IF NOT EXISTS chain_group_encryption_keys (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        thread_id text,
        group_id text,
        public_key text,
        key_version integer DEFAULT 1,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_key_rotation_events"] = """
    CREATE TABLE IF NOT EXISTS chain_key_rotation_events (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        thread_id text,
        group_id text,
        old_key_version integer,
        new_key_version integer,
        reason text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_live_chat_bans"] = """
    CREATE TABLE IF NOT EXISTS chain_live_chat_bans (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        room_id text,
        profile_id text,
        banned_by text,
        reason text,
        expires_at timestamptz,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_live_earnings"] = """
    CREATE TABLE IF NOT EXISTS chain_live_earnings (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL,
        room_id text,
        amount_cents integer DEFAULT 0,
        source text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_live_goals"] = """
    CREATE TABLE IF NOT EXISTS chain_live_goals (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        room_id text,
        profile_id text,
        target_amount integer DEFAULT 0,
        current_amount integer DEFAULT 0,
        title text,
        status text DEFAULT 'active',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_live_location_shares"] = """
    CREATE TABLE IF NOT EXISTS chain_live_location_shares (
        id text PRIMARY KEY,
        sender_profile_id text NOT NULL,
        thread_id text,
        latitude numeric,
        longitude numeric,
        is_active boolean DEFAULT true,
        created_at timestamptz DEFAULT now(),
        expires_at timestamptz,
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_live_participants"] = """
    CREATE TABLE IF NOT EXISTS chain_live_participants (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        room_id text,
        profile_id text,
        role text DEFAULT 'viewer',
        joined_at timestamptz DEFAULT now(),
        left_at timestamptz
    )
"""

AUTO_DDL["chain_live_raids"] = """
    CREATE TABLE IF NOT EXISTS chain_live_raids (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        from_room_id text,
        to_room_id text,
        from_profile_id text,
        participant_count integer DEFAULT 0,
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_message_poll_options"] = """
    CREATE TABLE IF NOT EXISTS chain_message_poll_options (
        id text PRIMARY KEY,
        poll_id text NOT NULL,
        option_text text,
        position integer DEFAULT 0,
        vote_count integer DEFAULT 0,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_message_poll_votes"] = """
    CREATE TABLE IF NOT EXISTS chain_message_poll_votes (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        poll_id text NOT NULL,
        option_id text NOT NULL,
        profile_id text NOT NULL,
        created_at timestamptz DEFAULT now(),
        UNIQUE(poll_id, profile_id)
    )
"""

AUTO_DDL["chain_message_polls"] = """
    CREATE TABLE IF NOT EXISTS chain_message_polls (
        id text PRIMARY KEY,
        sender_profile_id text NOT NULL,
        thread_id text,
        question text,
        allow_multiple_vote boolean DEFAULT false,
        status text DEFAULT 'active',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_message_requests"] = """
    CREATE TABLE IF NOT EXISTS chain_message_requests (
        id text PRIMARY KEY,
        from_profile_id text NOT NULL,
        to_profile_id text NOT NULL,
        message_body text,
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_moderation_actions"] = """
    CREATE TABLE IF NOT EXISTS chain_moderation_actions (
        id text PRIMARY KEY,
        moderator_profile_id text NOT NULL,
        target_profile_id text,
        content_id text,
        content_type text,
        action_type text,
        reason text,
        duration_minutes integer,
        metadata jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_moderation_logs"] = """
    CREATE TABLE IF NOT EXISTS chain_moderation_logs (
        id text PRIMARY KEY,
        actor_id text,
        target_id text,
        entity_id text,
        entity_type text,
        action text,
        reason text,
        ip_address text,
        details text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_moderation_queue"] = """
    CREATE TABLE IF NOT EXISTS chain_moderation_queue (
        id text PRIMARY KEY,
        profile_id text,
        content_id text,
        content_type text,
        queue_type text,
        risk_level text DEFAULT 'low',
        reason text,
        metadata jsonb DEFAULT '{}',
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_payment_intents"] = """
    CREATE TABLE IF NOT EXISTS chain_payment_intents (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        amount_cents integer DEFAULT 0,
        currency text DEFAULT 'usd',
        status text DEFAULT 'pending',
        provider text,
        provider_intent_id text,
        metadata jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_products"] = """
    CREATE TABLE IF NOT EXISTS chain_products (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        shop_id text,
        title text,
        description text,
        price_cents integer DEFAULT 0,
        category text,
        condition text,
        stock integer DEFAULT 0,
        tags jsonb DEFAULT '[]',
        status text DEFAULT 'active',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_restrictions"] = """
    CREATE TABLE IF NOT EXISTS chain_restrictions (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        restricted_by text,
        restriction_type text,
        reason text,
        status text DEFAULT 'active',
        duration_minutes integer,
        expires_at timestamptz,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_reviews"] = """
    CREATE TABLE IF NOT EXISTS chain_reviews (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text,
        target_id text,
        target_type text,
        rating integer DEFAULT 0,
        body text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_saved_products"] = """
    CREATE TABLE IF NOT EXISTS chain_saved_products (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        product_id text,
        service_id text,
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_services"] = """
    CREATE TABLE IF NOT EXISTS chain_services (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        shop_id text,
        title text,
        description text,
        category text,
        hourly_rate_cents integer DEFAULT 0,
        availability jsonb DEFAULT '{}',
        service_area text,
        status text DEFAULT 'active',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_shops"] = """
    CREATE TABLE IF NOT EXISTS chain_shops (
        id text PRIMARY KEY,
        profile_id text NOT NULL UNIQUE,
        name text,
        description text,
        category text,
        shop_type text DEFAULT 'individual',
        status text DEFAULT 'active',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_spam_events"] = """
    CREATE TABLE IF NOT EXISTS chain_spam_events (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        event_type text,
        content_id text,
        content_type text,
        score numeric DEFAULT 0,
        metadata jsonb DEFAULT '{}',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_thread_disappearing_settings"] = """
    CREATE TABLE IF NOT EXISTS chain_thread_disappearing_settings (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        thread_id text NOT NULL UNIQUE,
        timer_seconds integer DEFAULT 0,
        enabled boolean DEFAULT false,
        set_by_profile_id text,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_tips"] = """
    CREATE TABLE IF NOT EXISTS chain_tips (
        id text PRIMARY KEY,
        sender_profile_id text NOT NULL,
        receiver_profile_id text NOT NULL,
        amount_cents integer DEFAULT 0,
        message text,
        transaction_id text,
        status text DEFAULT 'completed',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_trust_scores"] = """
    CREATE TABLE IF NOT EXISTS chain_trust_scores (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL UNIQUE,
        score numeric DEFAULT 0,
        signals jsonb DEFAULT '{}',
        last_updated timestamptz DEFAULT now(),
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_user_reports"] = """
    CREATE TABLE IF NOT EXISTS chain_user_reports (
        id text PRIMARY KEY,
        reporter_profile_id text NOT NULL,
        reported_profile_id text,
        content_id text,
        content_type text,
        reason text,
        details text,
        severity text DEFAULT 'medium',
        status text DEFAULT 'pending',
        created_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_user_settings"] = """
    CREATE TABLE IF NOT EXISTS chain_user_settings (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id text NOT NULL UNIQUE,
        profile_visibility text DEFAULT 'public',
        show_online_status boolean DEFAULT true,
        allow_messages text DEFAULT 'everyone',
        allow_video_calls text DEFAULT 'everyone',
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

AUTO_DDL["chain_wallet_payouts"] = """
    CREATE TABLE IF NOT EXISTS chain_wallet_payouts (
        id text PRIMARY KEY,
        profile_id text NOT NULL,
        idempotency_key text,
        amount_nad integer DEFAULT 0,
        status text DEFAULT 'pending',
        payout_method text,
        notes text,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now()
    )
"""

ALL_TABLES = list(KNOWN_DDL.keys()) + list(AUTO_DDL.keys())

def table_exists(tbl):
    rows = fast_query(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s) AS exists",
        [tbl], timeout_ms=5000, default=[{"exists": False}]
    )
    return rows and rows[0].get("exists", False)

def main():
    print("=" * 72)
    print("MIGRATION — Creating missing database tables")
    print("=" * 72)

    created = 0
    skipped = 0
    failed = 0

    all_ddl = {**KNOWN_DDL, **AUTO_DDL}
    for tbl in sorted(ALL_TABLES):
        ddl = all_ddl[tbl]
        exists = table_exists(tbl)
        if exists:
            print(f"  SKIP  {tbl} (already exists)")
            skipped += 1
            continue
        try:
            write_query(ddl)
            # Create indexes for common lookups
            idx_sqls = [
                f"CREATE INDEX IF NOT EXISTS idx_{tbl}_profile_id ON {tbl}(profile_id)" if 'profile_id' in ddl else None,
            ]
            for idx_sql in idx_sqls:
                if idx_sql:
                    try:
                        write_query(idx_sql)
                    except Exception:
                        pass
            print(f"  OK    {tbl}")
            created += 1
        except Exception as e:
            print(f"  FAIL  {tbl}: {e}")
            failed += 1

    print("\n" + "=" * 72)
    print(f"Created: {created}  Skipped: {skipped}  Failed: {failed}")
    if failed:
        print("SOME TABLES FAILED — check errors above")
        return 1
    print("All tables created successfully.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
