-- Phase 123 — Homepage/Reels Performance Indexes (Plain SQL)
-- safe to run idempotently with CREATE INDEX IF NOT EXISTS
-- Run directly on Neon production database via `psql` or `npx pg-push`

-- chain_posts
CREATE INDEX IF NOT EXISTS idx_posts_created_active ON chain_posts (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_posts_profile_created_active ON chain_posts (profile_id, created_at DESC) WHERE deleted_at IS NULL;

-- chain_reels
CREATE INDEX IF NOT EXISTS idx_reels_created_active ON chain_reels (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_reels_profile_created_active ON chain_reels (profile_id, created_at DESC) WHERE deleted_at IS NULL;

-- chain_stories
CREATE INDEX IF NOT EXISTS idx_stories_created_active ON chain_stories (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_stories_profile_created_active ON chain_stories (profile_id, created_at DESC) WHERE deleted_at IS NULL;

-- chain_status_posts
CREATE INDEX IF NOT EXISTS idx_status_posts_created_active ON chain_status_posts (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_status_posts_profile_created_active ON chain_status_posts (profile_id, created_at DESC) WHERE deleted_at IS NULL;

-- chain_live_rooms
CREATE INDEX IF NOT EXISTS idx_live_rooms_created_active ON chain_live_rooms (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_live_rooms_is_live_created_active ON chain_live_rooms (is_live, created_at DESC) WHERE deleted_at IS NULL;

-- chain_profiles
CREATE INDEX IF NOT EXISTS idx_profiles_created_active ON chain_profiles (created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_followers_active ON chain_profiles (followers_count DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_profiles_creator_followers_active ON chain_profiles (is_creator, followers_count DESC) WHERE deleted_at IS NULL;

-- chain_reel_events
CREATE INDEX IF NOT EXISTS idx_reel_events_reel_created ON chain_reel_events (reel_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reel_events_user_created ON chain_reel_events (user_id, created_at DESC);
