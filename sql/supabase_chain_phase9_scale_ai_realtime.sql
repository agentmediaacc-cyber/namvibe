-- CHAIN Phase 9: High-Scale Real-Time & AI Experience
-- This migration adds Short Videos (Reels), Stream Analytics, and Advanced Social logic.

-- 1. Short Videos (Reels)
CREATE TABLE IF NOT EXISTS chain_reels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    video_url text NOT NULL,
    thumbnail_url text,
    caption text,
    music_id uuid REFERENCES chain_music_tracks(id) ON DELETE SET NULL,
    likes_count integer DEFAULT 0,
    comments_count integer DEFAULT 0,
    shares_count integer DEFAULT 0,
    view_count integer DEFAULT 0,
    is_private boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_reels_profile ON chain_reels(profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_reels_trending ON chain_reels(view_count DESC, created_at DESC);

-- 2. Stream Analytics
CREATE TABLE IF NOT EXISTS chain_stream_analytics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    host_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    peak_viewers integer DEFAULT 0,
    total_unique_viewers integer DEFAULT 0,
    total_watch_time_minutes interval DEFAULT '00:00:00',
    total_gift_coins numeric DEFAULT 0,
    total_reactions integer DEFAULT 0,
    started_at timestamptz,
    ended_at timestamptz,
    retention_rate numeric DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_stream_analytics_host ON chain_stream_analytics(host_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_stream_analytics_room ON chain_stream_analytics(room_id);

-- 3. AI Recommendations Cache
CREATE TABLE IF NOT EXISTS chain_ai_recommendations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    recommendation_type text NOT NULL, -- 'people', 'live_room', 'reel', 'marketplace'
    recommended_entity_id uuid NOT NULL,
    score numeric DEFAULT 0,
    reason text, -- e.g., 'Shared interests in Music'
    updated_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, recommendation_type, recommended_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_chain_ai_recommendations_user ON chain_ai_recommendations(profile_id, score DESC);

-- 4. Premium Membership Upgrades
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_profiles' AND COLUMN_NAME = 'premium_gold_badge') THEN
        ALTER TABLE chain_profiles ADD COLUMN premium_gold_badge boolean DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_profiles' AND COLUMN_NAME = 'visibility_boost') THEN
        ALTER TABLE chain_profiles ADD COLUMN visibility_boost numeric DEFAULT 1.0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_profiles' AND COLUMN_NAME = 'hd_streaming_enabled') THEN
        ALTER TABLE chain_profiles ADD COLUMN hd_streaming_enabled boolean DEFAULT false;
    END IF;
END $$;

-- 5. Auto-Moderation & Security
CREATE TABLE IF NOT EXISTS chain_moderation_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_type text NOT NULL, -- 'keyword', 'rate_limit', 'spam_pattern'
    pattern text NOT NULL,
    severity text DEFAULT 'low', -- 'low', 'medium', 'high'
    action text DEFAULT 'flag', -- 'flag', 'block', 'shadow_ban'
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

-- 6. Marketplace Subscriptions
CREATE TABLE IF NOT EXISTS chain_creator_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    creator_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    tier text DEFAULT 'premium',
    monthly_price numeric NOT NULL,
    expires_at timestamptz,
    status text DEFAULT 'active',
    created_at timestamptz DEFAULT now(),
    UNIQUE(subscriber_profile_id, creator_profile_id)
);

-- 7. Live Room Enhancements
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'slow_mode_seconds') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN slow_mode_seconds integer DEFAULT 0;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'stream_goal_coins') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN stream_goal_coins integer DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'stream_goal_current') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN stream_goal_current integer DEFAULT 0;
    END IF;
END $$;
