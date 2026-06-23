-- Phase 138: Homepage Performance Indexes
-- Safe partial indexes to fix homepage timeout
-- These indexes optimize queries for deleted_at, is_live, expires_at filters

-- Posts: active posts only
CREATE INDEX IF NOT EXISTS idx_chain_posts_homepage 
ON chain_posts (created_at DESC) 
WHERE deleted_at IS NULL;

-- Reels: active reels only
CREATE INDEX IF NOT EXISTS idx_chain_reels_homepage 
ON chain_reels (created_at DESC) 
WHERE deleted_at IS NULL;

-- Stories/Status posts: active only
CREATE INDEX IF NOT EXISTS idx_chain_stories_homepage 
ON chain_stories (created_at DESC) 
WHERE deleted_at IS NULL AND active = TRUE;

-- Status posts: active and not expired (immutable predicate)
CREATE INDEX IF NOT EXISTS idx_chain_status_posts_homepage 
ON chain_status_posts (created_at DESC) 
WHERE deleted_at IS NULL AND expires_at IS NULL;

-- Live rooms: live only
CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_homepage 
ON chain_live_rooms (created_at DESC) 
WHERE deleted_at IS NULL AND is_live = TRUE;

-- Profiles: creators only (for homepage creators section)
CREATE INDEX IF NOT EXISTS idx_chain_profiles_homepage 
ON chain_profiles (created_at DESC) 
WHERE deleted_at IS NULL AND is_creator = TRUE;

-- Notifications: for user notifications
CREATE INDEX IF NOT EXISTS idx_chain_notifications_homepage 
ON chain_notifications (created_at DESC) 
WHERE deleted_at IS NULL;

-- Follows: for quick follow count lookups
CREATE INDEX IF NOT EXISTS idx_chain_follows_lookup 
ON chain_follows (follower_profile_id, following_profile_id) 
WHERE deleted_at IS NULL;

-- Profile lookup by username (for profile links)
CREATE INDEX IF NOT EXISTS idx_chain_profiles_username 
ON chain_profiles (username) 
WHERE deleted_at IS NULL;

-- Profile lookup by id
CREATE INDEX IF NOT EXISTS idx_chain_profiles_id 
ON chain_profiles (id) 
WHERE deleted_at IS NULL;