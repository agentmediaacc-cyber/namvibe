-- ============================================================
-- PHASE 40: Premium WebRTC Calling Engine
-- Idempotent — safe to re-run
-- ============================================================

-- 1. chain_calls (NEW)
CREATE TABLE IF NOT EXISTS chain_calls (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    caller_profile_id UUID NOT NULL,
    receiver_profile_id UUID NOT NULL,
    thread_id       UUID,
    call_type       TEXT NOT NULL DEFAULT 'audio',
    call_mode       TEXT NOT NULL DEFAULT 'audio',
    status          TEXT NOT NULL DEFAULT 'ringing',
    started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    accepted_at     TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    duration_seconds INTEGER DEFAULT 0,
    end_reason      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. chain_call_logs (NEW)
CREATE TABLE IF NOT EXISTS chain_call_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_id         UUID REFERENCES chain_calls(id) ON DELETE CASCADE,
    profile_id      UUID NOT NULL,
    other_profile_id UUID,
    direction       TEXT NOT NULL DEFAULT 'outgoing',
    call_type       TEXT NOT NULL DEFAULT 'audio',
    status          TEXT NOT NULL DEFAULT 'missed',
    duration_seconds INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Upgrade chain_call_participants (EXISTS)
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS call_id UUID;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'participant';
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS muted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS camera_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS speaker_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS connection_status TEXT DEFAULT 'connecting';

-- 4. Upgrade chain_call_events (EXISTS)
ALTER TABLE chain_call_events ADD COLUMN IF NOT EXISTS call_id UUID;
ALTER TABLE chain_call_events ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE chain_call_events ALTER COLUMN payload SET DEFAULT '{}'::jsonb;

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_chain_calls_caller      ON chain_calls(caller_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_calls_receiver    ON chain_calls(receiver_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_calls_status      ON chain_calls(status);
CREATE INDEX IF NOT EXISTS idx_chain_calls_created_at  ON chain_calls(created_at);
CREATE INDEX IF NOT EXISTS idx_chain_calls_thread_id   ON chain_calls(thread_id);

CREATE INDEX IF NOT EXISTS idx_call_participants_call_id    ON chain_call_participants(call_id);
CREATE INDEX IF NOT EXISTS idx_call_participants_profile_id ON chain_call_participants(profile_id);

CREATE INDEX IF NOT EXISTS idx_call_events_call_id     ON chain_call_events(call_id);
CREATE INDEX IF NOT EXISTS idx_call_events_profile_id  ON chain_call_events(profile_id);

CREATE INDEX IF NOT EXISTS idx_call_logs_profile_id    ON chain_call_logs(profile_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_call_id       ON chain_call_logs(call_id);
CREATE INDEX IF NOT EXISTS idx_call_logs_created_at    ON chain_call_logs(created_at);
