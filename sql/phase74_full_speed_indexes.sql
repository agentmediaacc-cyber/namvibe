-- Phase 74 — Full App Upgrade + Speed Max
-- Targeted indexes for remaining slow query patterns.
-- All use IF NOT EXISTS for idempotent application.

-- 1. Creator profiles sorted by followers_count (trending creators)
CREATE INDEX IF NOT EXISTS idx_p74_profiles_creator_followers
    ON chain_profiles (followers_count DESC NULLS LAST)
    WHERE is_creator = TRUE AND deleted_at IS NULL;

-- 2. Lower-case town lookup for nearby users
CREATE INDEX IF NOT EXISTS idx_p74_profiles_lower_town
    ON chain_profiles (LOWER(town))
    WHERE deleted_at IS NULL AND town IS NOT NULL;

-- 3. Lower-case location lookup for nearby users
CREATE INDEX IF NOT EXISTS idx_p74_profiles_lower_location
    ON chain_profiles (LOWER(location))
    WHERE deleted_at IS NULL AND location IS NOT NULL;

-- 4. Unread notification count (frequent polling endpoint)
CREATE INDEX IF NOT EXISTS idx_p74_notifications_unread
    ON chain_notifications (recipient_profile_id, created_at DESC NULLS LAST)
    WHERE is_read = FALSE AND deleted_at IS NULL;

-- 5. Messages by thread, most recent first (inbox)
CREATE INDEX IF NOT EXISTS idx_p74_messages_thread_recent
    ON chain_messages (thread_id, created_at DESC NULLS LAST);

-- 6. Profile's message threads (inbox list)
CREATE INDEX IF NOT EXISTS idx_p74_thread_members_profile
    ON chain_thread_members (profile_id, thread_id);

-- 7. Active follows for follower lookup (follow feed)
CREATE INDEX IF NOT EXISTS idx_p74_follows_active_follower
    ON chain_follows (follower_profile_id, following_profile_id)
    WHERE deleted_at IS NULL;

-- 8. Active follows for following lookup (profile page)
CREATE INDEX IF NOT EXISTS idx_p74_follows_active_following
    ON chain_follows (following_profile_id, follower_profile_id)
    WHERE deleted_at IS NULL;

-- 9. Posts with public visibility, most recent (public feed)
CREATE INDEX IF NOT EXISTS idx_p74_posts_public_recent
    ON chain_posts (created_at DESC NULLS LAST)
    WHERE deleted_at IS NULL AND (visibility IS NULL OR visibility = 'public');

-- 10. Stories that are active and not deleted (story strip)
CREATE INDEX IF NOT EXISTS idx_p74_stories_active
    ON chain_stories (created_at DESC NULLS LAST)
    WHERE deleted_at IS NULL AND (status IS NULL OR status != 'deleted');

-- 11. Dating profiles with mode enabled (discover)
CREATE INDEX IF NOT EXISTS idx_p74_dating_profiles_active
    ON chain_profiles (created_at DESC NULLS LAST)
    WHERE dating_mode_enabled = TRUE AND deleted_at IS NULL;

-- 12. Wallet transactions by profile, most recent (wallet page)
CREATE INDEX IF NOT EXISTS idx_p74_wallet_tx_profile_recent
    ON chain_wallet_transactions (profile_id, created_at DESC NULLS LAST);

-- 13. Live rooms that are live, sorted by viewer count (live tab)
CREATE INDEX IF NOT EXISTS idx_p74_live_rooms_live_viewers
    ON chain_live_rooms (viewer_count DESC NULLS LAST)
    WHERE status = 'live' AND deleted_at IS NULL;

-- 14. Posts with engagement for trending (pre-computed sort)
CREATE INDEX IF NOT EXISTS idx_p74_posts_trending
    ON chain_posts ((COALESCE(likes_count, 0) + COALESCE(comments_count, 0)) DESC NULLS LAST)
    WHERE deleted_at IS NULL;
