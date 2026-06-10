-- ============================================================
-- PHASE 54 — PREMIUM MESSAGING, CALLS, WALLET, AI EXPERIENCE
-- Idempotent — safe to re-run
-- ============================================================

-- Voice note transcription
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS transcript TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS transcript_available BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS transcript_hidden BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS transcript_updated_at TIMESTAMPTZ;

-- Translation / AI metadata
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_translated_text TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_translated_language TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_suggested_reply TEXT;

-- HD media metadata
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_quality TEXT DEFAULT 'standard';
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_file_size BIGINT DEFAULT 0;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS original_file_name TEXT;

-- Scheduled message cancel/edit fields. Support both legacy names used by prior phases.
CREATE TABLE IF NOT EXISTS chain_message_scheduled (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id) ON DELETE CASCADE,
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    body TEXT,
    media_url TEXT,
    message_type TEXT DEFAULT 'text',
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'scheduled',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    sent_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancelled_by_profile_id UUID REFERENCES chain_profiles(id),
    cancel_reason TEXT
);
ALTER TABLE chain_message_scheduled ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_message_scheduled ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE chain_message_scheduled ADD COLUMN IF NOT EXISTS cancelled_by_profile_id UUID REFERENCES chain_profiles(id);
ALTER TABLE chain_message_scheduled ADD COLUMN IF NOT EXISTS cancel_reason TEXT;
ALTER TABLE chain_message_scheduled ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS chain_scheduled_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id) ON DELETE CASCADE,
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    body TEXT,
    media_url TEXT,
    message_type TEXT DEFAULT 'text',
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    sent_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    cancelled_by_profile_id UUID REFERENCES chain_profiles(id),
    cancel_reason TEXT
);
ALTER TABLE chain_scheduled_messages ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_scheduled_messages ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE chain_scheduled_messages ADD COLUMN IF NOT EXISTS cancelled_by_profile_id UUID REFERENCES chain_profiles(id);
ALTER TABLE chain_scheduled_messages ADD COLUMN IF NOT EXISTS cancel_reason TEXT;

-- Disappearing message expiry metadata. Messages are soft-deleted first.
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS expired_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS deletion_reason TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS deleted_for_everyone BOOLEAN DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS chain_thread_disappearing_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id) ON DELETE CASCADE,
    timer_seconds INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT FALSE,
    set_by_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(thread_id)
);

CREATE TABLE IF NOT EXISTS chain_live_location_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id) ON DELETE CASCADE,
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Call quality and missed-call reasons.
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS network_quality TEXT DEFAULT 'good';
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS reconnect_count INTEGER DEFAULT 0;
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS missed_reason TEXT;
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS end_reason TEXT;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS connection_status TEXT DEFAULT 'good';
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS last_quality_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS chain_call_quality_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id UUID,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    quality_status TEXT,
    ice_state TEXT,
    connection_state TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Search, scheduled, disappearing, live-location indexes.
CREATE INDEX IF NOT EXISTS idx_phase54_messages_thread_created
    ON chain_messages(thread_id, created_at DESC)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_phase54_messages_search
    ON chain_messages USING gin(to_tsvector('simple', COALESCE(body, '')))
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_phase54_messages_expiring
    ON chain_messages(thread_id, created_at, expired_at)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_phase54_scheduled_pending
    ON chain_message_scheduled(thread_id, status, scheduled_for)
    WHERE status IN ('scheduled', 'pending');
CREATE INDEX IF NOT EXISTS idx_phase54_scheduled_sender
    ON chain_message_scheduled(sender_profile_id, scheduled_for);
CREATE INDEX IF NOT EXISTS idx_phase54_legacy_scheduled_pending
    ON chain_scheduled_messages(thread_id, status, scheduled_for)
    WHERE status IN ('scheduled', 'pending');
CREATE INDEX IF NOT EXISTS idx_phase54_live_location_active
    ON chain_live_location_shares(thread_id, expires_at)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_phase54_call_quality
    ON chain_call_quality_events(call_id, created_at DESC);
