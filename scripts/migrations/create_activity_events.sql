-- Create chain_activity_events table for universal activity engine
-- Run this migration manually if the table does not exist.
-- Checked by activity_engine.py at import time.

CREATE TABLE IF NOT EXISTS chain_activity_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    target_type text,
    target_id text,
    metadata jsonb DEFAULT '{}'::jsonb,
    visibility text DEFAULT 'private',
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_activity_events_recipient_created
    ON chain_activity_events (recipient_profile_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_activity_events_actor_created
    ON chain_activity_events (actor_profile_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_activity_events_type_created
    ON chain_activity_events (event_type, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_activity_events_target
    ON chain_activity_events (target_type, target_id)
    WHERE deleted_at IS NULL;
