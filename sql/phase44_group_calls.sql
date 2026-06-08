-- ============================================================
-- PHASE 44: Group Audio & Video Calling Engine
-- Idempotent -- safe to re-run
-- ============================================================

-- 1. chain_group_calls
CREATE TABLE IF NOT EXISTS chain_group_calls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    host_profile_id UUID NOT NULL,
    thread_id UUID DEFAULT NULL,
    room_name TEXT NOT NULL DEFAULT '',
    call_type TEXT NOT NULL DEFAULT 'audio',
    status TEXT NOT NULL DEFAULT 'waiting',
    max_participants INTEGER DEFAULT 32,
    participant_count INTEGER DEFAULT 0,
    room_locked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    started_at TIMESTAMPTZ DEFAULT NULL,
    ended_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_group_calls_host ON chain_group_calls(host_profile_id);
CREATE INDEX IF NOT EXISTS idx_group_calls_status ON chain_group_calls(status);
CREATE INDEX IF NOT EXISTS idx_group_calls_created ON chain_group_calls(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_group_calls_thread ON chain_group_calls(thread_id);

-- 2. chain_group_call_participants
CREATE TABLE IF NOT EXISTS chain_group_call_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_call_id UUID NOT NULL REFERENCES chain_group_calls(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL,
    role TEXT NOT NULL DEFAULT 'participant',
    status TEXT NOT NULL DEFAULT 'joined',
    muted BOOLEAN DEFAULT FALSE,
    camera_enabled BOOLEAN DEFAULT TRUE,
    hand_raised BOOLEAN DEFAULT FALSE,
    screen_sharing BOOLEAN DEFAULT FALSE,
    speaking BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMPTZ DEFAULT now(),
    left_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_gcp_call ON chain_group_call_participants(group_call_id);
CREATE INDEX IF NOT EXISTS idx_gcp_profile ON chain_group_call_participants(profile_id);
CREATE INDEX IF NOT EXISTS idx_gcp_status ON chain_group_call_participants(status);

-- 3. chain_group_call_invites
CREATE TABLE IF NOT EXISTS chain_group_call_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_call_id UUID NOT NULL REFERENCES chain_group_calls(id) ON DELETE CASCADE,
    invited_profile_id UUID NOT NULL,
    invited_by_profile_id UUID NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gci_call ON chain_group_call_invites(group_call_id);
CREATE INDEX IF NOT EXISTS idx_gci_invited ON chain_group_call_invites(invited_profile_id);
CREATE INDEX IF NOT EXISTS idx_gci_status ON chain_group_call_invites(status);

-- 4. chain_group_call_events
CREATE TABLE IF NOT EXISTS chain_group_call_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_call_id UUID NOT NULL REFERENCES chain_group_calls(id) ON DELETE CASCADE,
    profile_id UUID DEFAULT NULL,
    event_type TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_gce_call ON chain_group_call_events(group_call_id);
CREATE INDEX IF NOT EXISTS idx_gce_profile ON chain_group_call_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_gce_created ON chain_group_call_events(created_at DESC);
