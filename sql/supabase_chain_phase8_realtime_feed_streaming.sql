-- CHAIN Phase 8: Real-time Social Experience & Premium Feed
-- This migration adds presence, live reactions, and feed-related structures.

-- 1. Real-time Presence tracking (improved)
CREATE TABLE IF NOT EXISTS chain_presence (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status text DEFAULT 'online', -- 'online', 'away', 'busy', 'offline'
    last_seen timestamptz DEFAULT now(),
    current_room_id uuid REFERENCES chain_live_rooms(id) ON DELETE SET NULL,
    device_type text, -- 'mobile', 'desktop', 'web'
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_presence_room ON chain_presence(current_room_id);
CREATE INDEX IF NOT EXISTS idx_chain_presence_status ON chain_presence(status);

-- 2. Live reactions with emoji support
CREATE TABLE IF NOT EXISTS chain_live_reactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reaction_type text NOT NULL, -- 'heart', 'fire', 'wow', 'clap', 'star', 'diamond'
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_live_reactions_room_time ON chain_live_reactions(room_id, created_at DESC);

-- 3. Extend live rooms for heartbeat and counters
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'last_heartbeat_at') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN last_heartbeat_at timestamptz DEFAULT now();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'reaction_count') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN reaction_count integer DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'is_featured') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN is_featured boolean DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'stream_quality') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN stream_quality text DEFAULT '720p';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'scheduled_at') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN scheduled_at timestamptz;
    END IF;
END $$;

-- 4. Follow system (if not already fully specified)
CREATE TABLE IF NOT EXISTS chain_follows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    following_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    is_premium_subscription boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    UNIQUE(follower_profile_id, following_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_chain_follows_follower ON chain_follows(follower_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_follows_following ON chain_follows(following_profile_id);

-- 5. Trending Scores
CREATE TABLE IF NOT EXISTS chain_trending_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL, -- 'profile', 'live_room', 'post', 'hashtag', 'track', 'marketplace_item'
    entity_id uuid NOT NULL,
    score numeric DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_trending_scores_lookup ON chain_trending_scores(entity_type, score DESC);

-- 6. User Interests for Feed
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_profiles' AND COLUMN_NAME = 'interests') THEN
        ALTER TABLE chain_profiles ADD COLUMN interests text[]; -- Array of interest tags
    END IF;
END $$;

-- 7. High-performance counter function
CREATE OR REPLACE FUNCTION increment_room_reactions(room_id uuid)
RETURNS void AS $$
BEGIN
    UPDATE chain_live_rooms
    SET reaction_count = reaction_count + 1,
        last_heartbeat_at = now()
    WHERE id = room_id;
END;
$$ LANGUAGE plpgsql;
