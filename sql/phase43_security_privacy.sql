-- ============================================================
-- PHASE 43: Security, Privacy, Device Management & Encryption
-- Idempotent -- safe to re-run
-- ============================================================

-- 1. chain_device_sessions
CREATE TABLE IF NOT EXISTS chain_device_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    device_name VARCHAR(255) DEFAULT '',
    device_type VARCHAR(50) DEFAULT '',
    browser VARCHAR(255) DEFAULT '',
    os VARCHAR(255) DEFAULT '',
    ip_hash VARCHAR(64) DEFAULT '',
    trusted BOOLEAN DEFAULT FALSE,
    last_seen TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now(),
    revoked_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_device_sessions_profile ON chain_device_sessions(profile_id);
CREATE INDEX IF NOT EXISTS idx_device_sessions_trusted ON chain_device_sessions(profile_id, trusted);
CREATE INDEX IF NOT EXISTS idx_device_sessions_last_seen ON chain_device_sessions(profile_id, last_seen DESC);

-- 2. chain_security_events
CREATE TABLE IF NOT EXISTS chain_security_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    device_id UUID DEFAULT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_security_events_profile ON chain_security_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_security_events_profile_created ON chain_security_events(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON chain_security_events(profile_id, event_type);

-- 3. chain_privacy_settings
CREATE TABLE IF NOT EXISTS chain_privacy_settings (
    profile_id UUID PRIMARY KEY,
    show_online_status BOOLEAN DEFAULT TRUE,
    show_last_seen BOOLEAN DEFAULT TRUE,
    show_read_receipts BOOLEAN DEFAULT TRUE,
    show_typing_indicator BOOLEAN DEFAULT TRUE,
    show_profile_photo BOOLEAN DEFAULT TRUE,
    allow_calls BOOLEAN DEFAULT TRUE,
    allow_group_invites BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_privacy_settings_profile ON chain_privacy_settings(profile_id);

-- 4. chain_encryption_keys
CREATE TABLE IF NOT EXISTS chain_encryption_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    public_key TEXT NOT NULL,
    key_version INTEGER DEFAULT 1,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_encryption_keys_profile ON chain_encryption_keys(profile_id);
CREATE INDEX IF NOT EXISTS idx_encryption_keys_active ON chain_encryption_keys(profile_id, active);

-- 5. chain_trusted_devices
CREATE TABLE IF NOT EXISTS chain_trusted_devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    device_session_id UUID NOT NULL REFERENCES chain_device_sessions(id) ON DELETE CASCADE,
    trusted_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trusted_devices_profile ON chain_trusted_devices(profile_id);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_session ON chain_trusted_devices(device_session_id);

-- notifications: ensure chain_security_events has the right metadata for notification surfacing
-- This is handled at the application layer via chain_security_events event_type filtering
