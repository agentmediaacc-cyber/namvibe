-- Phase 77: Optimize message queries
-- Run: psql $DATABASE_URL -f migrations/002_messages_indexes.sql

-- Composite index for list_threads() query (member + thread + timestamp)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_thread_members_profile_thread
    ON chain_thread_members (profile_id, thread_id);

-- Composite index for get_thread() messages query (thread + timestamp)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_thread_created
    ON chain_messages (thread_id, created_at ASC)
    WHERE deleted_at IS NULL;

-- Composite index for unread counts (thread + sender + seen)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_unread
    ON chain_messages (thread_id, sender_profile_id)
    WHERE is_seen = FALSE AND deleted_at IS NULL;

-- Index for deduplication and delivery tracking
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_messages_sender_created
    ON chain_messages (sender_profile_id, created_at DESC);
