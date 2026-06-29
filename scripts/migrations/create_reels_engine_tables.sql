-- Reels Engine Phase 4 Migration
-- Run after verifying chain_reels exists

-- Reel saves (separate from generic engagement service saves)
CREATE TABLE IF NOT EXISTS chain_reel_saves (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reel_id BIGINT NOT NULL REFERENCES chain_reels(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, reel_id)
);

CREATE INDEX IF NOT EXISTS idx_reel_saves_profile ON chain_reel_saves(profile_id);
CREATE INDEX IF NOT EXISTS idx_reel_saves_reel ON chain_reel_saves(reel_id);

-- Detailed watch events (per-user, per-session replay tracking)
CREATE TABLE IF NOT EXISTS chain_reel_watch_events (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reel_id BIGINT NOT NULL REFERENCES chain_reels(id) ON DELETE CASCADE,
    watch_ms INTEGER NOT NULL DEFAULT 0,
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    replayed BOOLEAN NOT NULL DEFAULT FALSE,
    watched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reel_watch_profile ON chain_reel_watch_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_reel_watch_reel ON chain_reel_watch_events(reel_id);
CREATE INDEX IF NOT EXISTS idx_reel_watch_completed ON chain_reel_watch_events(reel_id, completed);

-- Reel shares with target info
CREATE TABLE IF NOT EXISTS chain_reel_shares (
    id BIGSERIAL PRIMARY KEY,
    profile_id BIGINT REFERENCES chain_profiles(id) ON DELETE SET NULL,
    reel_id BIGINT NOT NULL REFERENCES chain_reels(id) ON DELETE CASCADE,
    target VARCHAR(32) DEFAULT 'link',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reel_shares_reel ON chain_reel_shares(reel_id);

-- Add saves_count column to chain_reels if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_reels' AND column_name = 'saves_count'
    ) THEN
        ALTER TABLE chain_reels ADD COLUMN saves_count INTEGER NOT NULL DEFAULT 0;
    END IF;
END $$;
