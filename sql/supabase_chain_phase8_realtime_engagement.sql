-- CHAIN Phase 8: Real-time Social Engagement Engine
-- This migration adds tables for follows, reactions, presence, and trending logic.

-- Follows tracking
CREATE TABLE IF NOT EXISTS chain_follows (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    follower_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    following_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE(follower_profile_id, following_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_chain_follows_follower ON chain_follows(follower_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_follows_following ON chain_follows(following_profile_id);

-- Post reactions (likes, hearts, etc.)
CREATE TABLE IF NOT EXISTS chain_post_reactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    post_id uuid REFERENCES chain_posts(id) ON DELETE CASCADE,
    reaction_type text DEFAULT 'like',
    created_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, post_id, reaction_type)
);

CREATE INDEX IF NOT EXISTS idx_chain_post_reactions_post ON chain_post_reactions(post_id);

-- Post comments
CREATE TABLE IF NOT EXISTS chain_post_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    post_id uuid REFERENCES chain_posts(id) ON DELETE CASCADE,
    body text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_post_comments_post ON chain_post_comments(post_id);

-- Live room reactions
CREATE TABLE IF NOT EXISTS chain_live_reactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reaction_type text NOT NULL,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_live_reactions_room ON chain_live_reactions(room_id);

-- Live room comments (if not already handled by chain_live_comments)
CREATE TABLE IF NOT EXISTS chain_live_comments_v2 (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    body text NOT NULL,
    created_at timestamptz DEFAULT now()
);

-- Typing status (ephemeral tracking)
CREATE TABLE IF NOT EXISTS chain_typing_status (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES chain_conversations(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    is_typing boolean DEFAULT false,
    updated_at timestamptz DEFAULT now(),
    UNIQUE(conversation_id, profile_id)
);

-- Online presence tracking
CREATE TABLE IF NOT EXISTS chain_online_presence (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    is_online boolean DEFAULT false,
    last_seen timestamptz DEFAULT now(),
    current_status text DEFAULT 'online', -- 'online', 'away', 'busy'
    updated_at timestamptz DEFAULT now()
);

-- Bookmarks / Saved items
CREATE TABLE IF NOT EXISTS chain_saved_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    item_type text NOT NULL, -- 'post', 'live_room', 'marketplace_item'
    item_id uuid NOT NULL,
    created_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, item_type, item_id)
);

-- Advanced Notification Events (extending/replacing chain_notifications)
CREATE TABLE IF NOT EXISTS chain_notification_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    event_type text NOT NULL, -- 'follow', 'reaction', 'comment', 'gift', 'live_start'
    title text,
    body text,
    target_url text,
    is_read boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_notifications_profile ON chain_notification_events(profile_id);

-- Trending scores (background calculation result)
CREATE TABLE IF NOT EXISTS chain_trending_scores (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL, -- 'profile', 'live_room', 'post', 'hashtag'
    entity_id uuid NOT NULL,
    score numeric DEFAULT 0,
    reason text,
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_trending_scores_type ON chain_trending_scores(entity_type, score DESC);
