-- Phase 11: Performance Hotspot Fixes
-- Run: psql $DATABASE_URL -f migrations/004_performance_hotfix_indexes.sql
-- Adds indexes for slow routes: /messages/, /stories, /api/stories/feed, /calls/recent, profile lookups

-- =========== MESSAGES INBOX ===========

-- Index for thread member lookups in list_threads()
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_thread_members_profile_pinned
    ON chain_thread_members (profile_id, is_pinned DESC, last_read_at DESC)
    WHERE deleted_at IS NULL;

-- Index for message thread updates ordering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_message_threads_updated
    ON chain_message_threads (updated_at DESC)
    WHERE deleted_at IS NULL;

-- Index for thread members join optimization
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_thread_members_thread_profile
    ON chain_thread_members (thread_id, profile_id)
    WHERE deleted_at IS NULL;

-- Index for unread count filtering in list_threads (is_seen + created_at)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_unread_optimized
    ON chain_messages (thread_id, sender_profile_id, is_seen, created_at DESC)
    WHERE deleted_at IS NULL;

-- =========== STORIES FEED ===========

-- Index for stories feed query (expires + visibility + created_at)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_posts_feed
    ON chain_status_posts (expires_at, created_at DESC)
    WHERE deleted_at IS NULL;

-- Composite index for the optimized feed query with visibility filtering
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_posts_visibility_feed
    ON chain_status_posts (expires_at, visibility, created_at DESC)
    WHERE deleted_at IS NULL;

-- Index for story views count subquery
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_story_views_story
    ON chain_story_views (story_id);

-- Index for profile lookups in stories join
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_id_deleted
    ON chain_profiles (id)
    WHERE deleted_at IS NULL;

-- Index for the follow_map CTE in list_active_statuses
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_follows_follower_following
    ON chain_follows (follower_profile_id, following_profile_id)
    WHERE deleted_at IS NULL;

-- =========== CALLS RECENT ===========

-- Index for recent calls query (caller/receiver + started_at) - covering for caller
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_sessions_caller_covering
    ON chain_call_sessions (caller_profile_id, started_at DESC)
    INCLUDE (conversation_id, call_type, call_status, ended_at, duration_seconds, receiver_profile_id);

-- Index for recent calls query - covering for receiver
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_sessions_receiver_covering
    ON chain_call_sessions (receiver_profile_id, started_at DESC)
    INCLUDE (conversation_id, call_type, call_status, ended_at, duration_seconds, caller_profile_id);

-- =========== PROFILE LOOKUPS ===========

-- Covering index for lightweight profile lookups (username, full_name, avatar_url, is_verified)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_lookup_covering
    ON chain_profiles (id, username, full_name, avatar_url, is_verified, deleted_at)
    WHERE deleted_at IS NULL;

-- Index for auth_user_id lookups (already exists in 003, but ensure covering)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_auth_covering
    ON chain_profiles (auth_user_id, id, username, deleted_at)
    WHERE deleted_at IS NULL;

-- Covering index for lightweight full profile lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_lightweight_full
    ON chain_profiles (id, auth_user_id, username, display_name, full_name, avatar_url, cover_url, bio, is_verified, email, email_verified, is_premium, premium_tier, is_public, followers_count, following_count, profile_completed, created_at, deleted_at)
    WHERE deleted_at IS NULL;

-- =========== MESSAGE QUERIES ===========

-- Index for message deletions check (in get_thread)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_message_deletions_message_profile
    ON chain_message_deletions (message_id, profile_id);

-- Index for thread members in get_thread LATERAL join
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_thread_members_thread_exclude
    ON chain_thread_members (thread_id, profile_id)
    WHERE deleted_at IS NULL;

-- =========== FRIENDS / FOLLOWS ===========

-- Index for mutual friends query in /api/friends
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_follows_mutual
    ON chain_follows (follower_profile_id, following_profile_id)
    WHERE deleted_at IS NULL;

-- =========== SAFETY: Use IF NOT EXISTS ===========
-- All indexes above use CONCURRENTLY IF NOT EXISTS for safe re-runs
-- No destructive operations - only additive indexes