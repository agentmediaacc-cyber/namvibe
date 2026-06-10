-- ============================================================
-- PHASE 53 — PREMIUM MESSAGING
-- Idempotent — safe to re-run
-- ============================================================

-- === 1. VOICE NOTE TRANSCRIPTION ===
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS transcript TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS transcript_available BOOLEAN DEFAULT FALSE;

-- === 2. HD MEDIA ===
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_quality TEXT DEFAULT 'standard';
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_file_size BIGINT DEFAULT 0;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS original_file_name TEXT;

-- === 3. SCHEDULED MESSAGES ===
CREATE TABLE IF NOT EXISTS chain_scheduled_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    body TEXT,
    media_url TEXT,
    message_type TEXT DEFAULT 'text',
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    sent_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_scheduled_messages_status
    ON chain_scheduled_messages(status, scheduled_for)
    WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_scheduled_messages_thread
    ON chain_scheduled_messages(thread_id);

-- === 4. POLL MESSAGES ===
CREATE TABLE IF NOT EXISTS chain_message_polls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    question TEXT NOT NULL,
    allow_multiple_vote BOOLEAN DEFAULT FALSE,
    is_closed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    closed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS chain_message_poll_options (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id UUID NOT NULL REFERENCES chain_message_polls(id) ON DELETE CASCADE,
    option_text TEXT NOT NULL,
    position INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS chain_message_poll_votes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id UUID NOT NULL REFERENCES chain_message_polls(id) ON DELETE CASCADE,
    option_id UUID NOT NULL REFERENCES chain_message_poll_options(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(poll_id, option_id, profile_id)
);
CREATE INDEX IF NOT EXISTS idx_poll_votes_poll
    ON chain_message_poll_votes(poll_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_message_polls_thread
    ON chain_message_polls(thread_id);

-- === 5. LIVE LOCATION SHARING ===
CREATE TABLE IF NOT EXISTS chain_live_location_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_live_location_active
    ON chain_live_location_shares(thread_id, is_active)
    WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_live_location_sender
    ON chain_live_location_shares(sender_profile_id);

-- === 6. DISAPPEARING MESSAGES ===
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

-- === 7. WALLET CHAT TRANSACTIONS ===
CREATE TABLE IF NOT EXISTS chain_chat_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    recipient_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    amount DOUBLE PRECISION NOT NULL,
    currency TEXT DEFAULT 'CHAIN',
    transaction_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_chat_transactions_thread
    ON chain_chat_transactions(thread_id);

-- === 8. AI CHAT TOOLS ===
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_translated_text TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS ai_suggested_reply TEXT;
