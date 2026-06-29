-- Reels Engine Phase 4 Migration (FIXED: UUID types)
-- Run after verifying chain_reels exists

-- Reel saves
CREATE TABLE IF NOT EXISTS chain_reel_saves (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reel_id UUID NOT NULL REFERENCES chain_reels(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, reel_id)
);

CREATE INDEX IF NOT EXISTS idx_reel_saves_profile ON chain_reel_saves(profile_id);
CREATE INDEX IF NOT EXISTS idx_reel_saves_reel ON chain_reel_saves(reel_id);

-- Reel shares with target info
CREATE TABLE IF NOT EXISTS chain_reel_shares (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    reel_id UUID NOT NULL REFERENCES chain_reels(id) ON DELETE CASCADE,
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
