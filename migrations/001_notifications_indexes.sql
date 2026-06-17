-- Phase 77: Optimize notification queries
-- Run: psql $DATABASE_URL -f migrations/001_notifications_indexes.sql

-- Composite index for list_notifications_tab() queries (recipient + timestamp)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_recipient_created
    ON chain_notifications (recipient_profile_id, created_at DESC);

-- Partial index for unread_count() query
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_unread
    ON chain_notifications (recipient_profile_id)
    WHERE is_read = FALSE AND deleted_at IS NULL;

-- Composite index for tab-filtered queries (recipient + type + timestamp)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_notifications_recipient_type_created
    ON chain_notifications (recipient_profile_id, event_type, created_at DESC);
