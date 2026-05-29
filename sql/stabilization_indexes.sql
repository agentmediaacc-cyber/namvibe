-- CHAIN Platform Stabilization Indexes
-- Optimized for high-frequency queries and feed performance

-- 1. Notification Unread Count (Partial Index)
-- This makes the SELECT COUNT(*) where is_read = false extremely fast
CREATE INDEX IF NOT EXISTS idx_chain_notifications_unread_partial 
ON chain_notifications (recipient_profile_id) 
WHERE is_read = FALSE AND deleted_at IS NULL;

-- 2. Notification List view
CREATE INDEX IF NOT EXISTS idx_chain_notifications_recipient_created 
ON chain_notifications (recipient_profile_id, created_at DESC) 
WHERE deleted_at IS NULL;

-- 3. Feed: Posts
CREATE INDEX IF NOT EXISTS idx_chain_posts_feed_v2 
ON chain_posts (visibility, deleted_at, created_at DESC);

-- 4. Feed: Reels
CREATE INDEX IF NOT EXISTS idx_chain_reels_feed_v2 
ON chain_reels (visibility, status, processing_status, deleted_at, created_at DESC);

-- 5. Feed: Live Rooms
CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_active_v2 
ON chain_live_rooms (deleted_at, is_live, created_at DESC) 
WHERE is_live = TRUE;

-- 6. Follow Affinity (for feed ranking)
CREATE INDEX IF NOT EXISTS idx_chain_follows_follower_following 
ON chain_follows (follower_profile_id, following_profile_id) 
WHERE deleted_at IS NULL;

-- 7. Moderation status (for feed filtering)
CREATE INDEX IF NOT EXISTS idx_chain_posts_moderation 
ON chain_posts (moderation_status) 
WHERE moderation_status != 'clean';
