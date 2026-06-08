-- Phase 37: Message + Call Runtime Fix
-- Safe migration: CREATE IF NOT EXISTS, no data loss

-- ========== MESSAGING TABLES ==========

CREATE TABLE IF NOT EXISTS chain_message_threads (
    id UUID PRIMARY KEY,
    created_by_profile_id UUID REFERENCES chain_profiles(id),
    thread_type TEXT NOT NULL DEFAULT 'direct',
    thread_name TEXT,
    thread_avatar_url TEXT,
    group_id UUID,
    folder_type TEXT DEFAULT 'primary',
    is_e2ee BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_thread_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    role TEXT DEFAULT 'member',
    muted BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    last_read_at TIMESTAMPTZ,
    last_read_message_id UUID,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(thread_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_messages (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL REFERENCES chain_message_threads(id),
    sender_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    body TEXT,
    message_type TEXT DEFAULT 'text',
    media_url TEXT,
    media_type TEXT,
    storage_bucket TEXT,
    storage_path TEXT,
    file_url TEXT,
    audio_url TEXT,
    voice_duration_seconds INTEGER,
    client_event_id TEXT,
    parent_message_id UUID,
    is_forwarded BOOLEAN DEFAULT FALSE,
    status_id UUID,
    delivery_status TEXT DEFAULT 'sent',
    is_delivered BOOLEAN DEFAULT FALSE,
    delivered_at TIMESTAMPTZ,
    is_seen BOOLEAN DEFAULT FALSE,
    seen_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    sticker_id TEXT,
    gif_url TEXT,
    location_lat DOUBLE PRECISION,
    location_lng DOUBLE PRECISION,
    contact_data JSONB,
    is_deleted BOOLEAN DEFAULT FALSE
);

-- ========== MESSAGING INDEXES ==========

CREATE INDEX IF NOT EXISTS idx_chain_messages_thread_created
    ON chain_messages(thread_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_messages_sender
    ON chain_messages(sender_profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_messages_client_event
    ON chain_messages(client_event_id);

CREATE INDEX IF NOT EXISTS idx_chain_thread_members_profile
    ON chain_thread_members(profile_id, thread_id);

CREATE INDEX IF NOT EXISTS idx_chain_thread_members_thread
    ON chain_thread_members(thread_id);

CREATE INDEX IF NOT EXISTS idx_chain_thread_members_profile_id
    ON chain_thread_members(profile_id);

-- ========== DELIVERY EVENTS ==========

CREATE TABLE IF NOT EXISTS chain_message_delivery_events (
    id UUID PRIMARY KEY,
    message_id UUID,
    thread_id UUID,
    sender_profile_id UUID,
    recipient_profile_id UUID,
    event_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_delivery_message
    ON chain_message_delivery_events(message_id);

CREATE INDEX IF NOT EXISTS idx_chain_delivery_recipient
    ON chain_message_delivery_events(recipient_profile_id);

-- ========== CALL TABLES ==========

CREATE TABLE IF NOT EXISTS chain_call_sessions (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES chain_message_threads(id),
    caller_profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    receiver_profile_id UUID REFERENCES chain_profiles(id),
    call_type TEXT DEFAULT 'video',
    call_status TEXT DEFAULT 'ringing',
    room_id TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER DEFAULT 0,
    is_group_call BOOLEAN DEFAULT FALSE,
    parent_call_session_id UUID,
    call_quality TEXT,
    screen_share_enabled BOOLEAN DEFAULT FALSE,
    reconnect_state TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_call_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL REFERENCES chain_call_sessions(id),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id),
    status TEXT DEFAULT 'invited',
    joined_at TIMESTAMPTZ,
    left_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL REFERENCES chain_call_sessions(id),
    profile_id UUID REFERENCES chain_profiles(id),
    event_type TEXT NOT NULL,
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ========== CALL INDEXES ==========

CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_caller
    ON chain_call_sessions(caller_profile_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_receiver
    ON chain_call_sessions(receiver_profile_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_status
    ON chain_call_sessions(call_status);

CREATE INDEX IF NOT EXISTS idx_chain_call_participants_session
    ON chain_call_participants(call_session_id);

CREATE INDEX IF NOT EXISTS idx_chain_call_participants_profile
    ON chain_call_participants(profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_call_events_session
    ON chain_call_events(call_session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_call_events_type
    ON chain_call_events(event_type);

-- ========== MESSAGE THREADS UPDATED_AT TRIGGER ==========

CREATE OR REPLACE FUNCTION update_thread_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE chain_message_threads SET updated_at = now() WHERE id = NEW.thread_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_update_thread_timestamp'
    ) THEN
        CREATE TRIGGER trg_update_thread_timestamp
        AFTER INSERT ON chain_messages
        FOR EACH ROW
        EXECUTE FUNCTION update_thread_timestamp();
    END IF;
END;
$$;
