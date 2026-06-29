-- Phase 113: Production Performance Optimizations
-- Run: psql $DATABASE_URL -f migrations/005_production_optimization_indexes.sql
-- Adds additional indexes for the 4 optimized routes

-- =========== MESSAGES INBOX (/messages/) ===========

-- Index for thread name/avatar column lookups already in 004
-- No additional indexes needed - query structure already optimized

-- =========== STORIES FEED (/stories, /api/stories/feed) ===========

-- Index for stories_engine.py get_story_feed with ANY(array) lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_status_posts_profile_visibility
    ON chain_status_posts (profile_id, visibility, expires_at, created_at DESC)
    WHERE deleted_at IS NULL;

-- Index for close_friends lookups in stories_engine.py
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_story_close_friends_profile
    ON chain_story_close_friends (profile_id, friend_id);

-- Index for hidden_from lookups in stories_engine.py
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_story_hidden_from_profile
    ON chain_story_hidden_from (profile_id, hidden_user_id);

-- =========== CALLS RECENT (/calls/recent) ===========

-- Composite index for UNION-based recent calls query (both caller and receiver in one scan)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_sessions_caller_receiver_started
    ON chain_call_sessions (caller_profile_id, started_at DESC)
    WHERE call_status IS NOT NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_sessions_receiver_started
    ON chain_call_sessions (receiver_profile_id, started_at DESC)
    WHERE call_status IS NOT NULL;

-- =========== PROFILE LOOKUPS ===========

-- Lightweight profile columns used in batch lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_lightweight_covering
    ON chain_profiles (id, username, full_name, avatar_url, is_verified)
    WHERE deleted_at IS NULL;

-- =========== SAFETY: All indexes use CONCURRENTLY IF NOT EXISTS ===========
-- No destructive operations - only additive indexes