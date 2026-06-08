-- ============================================================
-- PHASE 46: True End-to-End Encryption Activation
-- Idempotent -- safe to re-run
-- ============================================================

-- 1. chain_encrypted_sessions
CREATE TABLE IF NOT EXISTS chain_encrypted_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    peer_profile_id UUID DEFAULT NULL,
    thread_id UUID DEFAULT NULL,
    session_type TEXT NOT NULL DEFAULT 'direct',
    session_key_id TEXT NOT NULL DEFAULT '',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    rotated_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_enc_sessions_profile ON chain_encrypted_sessions(profile_id);
CREATE INDEX IF NOT EXISTS idx_enc_sessions_peer ON chain_encrypted_sessions(peer_profile_id);
CREATE INDEX IF NOT EXISTS idx_enc_sessions_thread ON chain_encrypted_sessions(thread_id);
CREATE INDEX IF NOT EXISTS idx_enc_sessions_active ON chain_encrypted_sessions(active);

-- 2. chain_group_encryption_keys
CREATE TABLE IF NOT EXISTS chain_group_encryption_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID DEFAULT NULL,
    thread_id UUID DEFAULT NULL,
    key_version INTEGER DEFAULT 1,
    public_key TEXT NOT NULL DEFAULT '',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    rotated_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_group_enc_keys_group ON chain_group_encryption_keys(group_id);
CREATE INDEX IF NOT EXISTS idx_group_enc_keys_thread ON chain_group_encryption_keys(thread_id);

-- 3. chain_key_rotation_events
CREATE TABLE IF NOT EXISTS chain_key_rotation_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID DEFAULT NULL,
    thread_id UUID DEFAULT NULL,
    group_id UUID DEFAULT NULL,
    old_key_version INTEGER DEFAULT 0,
    new_key_version INTEGER DEFAULT 1,
    reason TEXT NOT NULL DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_key_rotation_profile ON chain_key_rotation_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_key_rotation_thread ON chain_key_rotation_events(thread_id);

-- 4. Add encryption columns to chain_messages
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS encrypted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS encryption_version INTEGER DEFAULT 1;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS encrypted_payload JSONB DEFAULT NULL;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS encryption_session_id UUID DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_messages_encrypted ON chain_messages(encrypted);
CREATE INDEX IF NOT EXISTS idx_messages_enc_session ON chain_messages(encryption_session_id);

-- 5. Add encryption columns to chain_call_events
ALTER TABLE chain_call_events ADD COLUMN IF NOT EXISTS encrypted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_call_events ADD COLUMN IF NOT EXISTS encrypted_payload JSONB DEFAULT NULL;

-- 6. Add E2EE columns to chain_message_threads
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS is_e2ee BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS e2ee_key_version INTEGER DEFAULT 1;
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS e2ee_activated_at TIMESTAMPTZ DEFAULT NULL;

-- 7. Add encrypted_private_key column to chain_encryption_keys for storage
ALTER TABLE chain_encryption_keys ADD COLUMN IF NOT EXISTS encrypted_private_key TEXT DEFAULT NULL;

-- ============================================================
-- PHASE 46.1: Performance Hotfix Indexes
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_messages_thread_sender_seen
ON chain_messages(thread_id, sender_profile_id, is_seen);

CREATE INDEX IF NOT EXISTS idx_thread_members_profile_thread
ON chain_thread_members(profile_id, thread_id);

CREATE INDEX IF NOT EXISTS idx_push_tokens_profile_active
ON chain_push_tokens(profile_id, active);

CREATE INDEX IF NOT EXISTS idx_notification_preferences_profile
ON chain_notification_preferences(profile_id);
