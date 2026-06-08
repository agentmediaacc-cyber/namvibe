-- ============================================================
-- PHASE 41: Mobile Call Reliability, Push Notifications, Call Log Polish
-- Idempotent — safe to re-run
-- ============================================================

-- 1. chain_call_notifications (NEW)
CREATE TABLE IF NOT EXISTS chain_call_notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL,
    call_id         UUID,
    notification_type TEXT NOT NULL,
    title           TEXT,
    body            TEXT,
    seen            BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. chain_call_quality_events (NEW)
CREATE TABLE IF NOT EXISTS chain_call_quality_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id         UUID NOT NULL,
    profile_id      UUID,
    quality_status  TEXT,
    ice_state       TEXT,
    connection_state TEXT,
    metadata        JSONB DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Add group call columns to chain_call_participants
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS speaking BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS left_at TIMESTAMPTZ;

-- 4. Add call_mode to chain_call_participants (group vs p2p)
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS call_mode TEXT DEFAULT 'p2p';

-- 5. Indexes for notifications
CREATE INDEX IF NOT EXISTS idx_call_notif_profile_id   ON chain_call_notifications(profile_id);
CREATE INDEX IF NOT EXISTS idx_call_notif_call_id      ON chain_call_notifications(call_id);
CREATE INDEX IF NOT EXISTS idx_call_notif_seen         ON chain_call_notifications(seen);
CREATE INDEX IF NOT EXISTS idx_call_notif_created_at   ON chain_call_notifications(created_at);

-- 6. Indexes for quality events
CREATE INDEX IF NOT EXISTS idx_call_quality_call_id    ON chain_call_quality_events(call_id);
CREATE INDEX IF NOT EXISTS idx_call_quality_profile_id ON chain_call_quality_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_call_quality_created_at ON chain_call_quality_events(created_at);

-- 7. Add invite-only column to chain_calls for group calls
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS is_group BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS participant_limit INTEGER DEFAULT 8;
