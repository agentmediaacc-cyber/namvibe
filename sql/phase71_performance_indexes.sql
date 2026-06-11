-- Phase 71 — Premium Speed + UI Polish: Performance Indexes
-- Idempotent — safe to re-run

-- 1. chain_follows: bidirectional mutual-friend lookups
CREATE INDEX IF NOT EXISTS idx_p71_follows_follower_following_deleted
    ON chain_follows (follower_profile_id, following_profile_id)
    WHERE deleted_at IS NULL;

-- 2. chain_messages: delivery-status updates (sent→delivered→seen)
CREATE INDEX IF NOT EXISTS idx_p71_messages_thread_delivery
    ON chain_messages (thread_id, delivery_status)
    WHERE delivery_status IN ('sent', 'delivered');

-- 3. chain_messages: unread counting for inbox
CREATE INDEX IF NOT EXISTS idx_p71_messages_thread_sender_unread
    ON chain_messages (thread_id, sender_profile_id, is_seen)
    WHERE is_seen = false;

-- 4. chain_notifications: filtered by event_type
CREATE INDEX IF NOT EXISTS idx_p71_notifications_recipient_event_created
    ON chain_notifications (recipient_profile_id, event_type, created_at DESC);

-- 5. chain_call_logs: history with specific other user
CREATE INDEX IF NOT EXISTS idx_p71_call_logs_profile_other_created
    ON chain_call_logs (profile_id, other_profile_id, created_at DESC);

-- 6. chain_wallet_transactions: filtered by type
CREATE INDEX IF NOT EXISTS idx_p71_wallet_tx_profile_type
    ON chain_wallet_transactions (profile_id, transaction_type);

-- 7. chain_posts: user's posts with engagement columns (covering for dashboard)
CREATE INDEX IF NOT EXISTS idx_p71_posts_profile_engagement
    ON chain_posts (profile_id, created_at DESC)
    INCLUDE (likes_count, comments_count);

-- 8. chain_reels: user's reels listing
CREATE INDEX IF NOT EXISTS idx_p71_reels_profile_created_desc
    ON chain_reels (profile_id, created_at DESC);

-- 9. chain_stories: active stories for user
CREATE INDEX IF NOT EXISTS idx_p71_stories_profile_active
    ON chain_stories (profile_id, deleted_at)
    WHERE deleted_at IS NULL;

-- 10. chain_live_rooms: discover by host
CREATE INDEX IF NOT EXISTS idx_p71_live_rooms_profile_status
    ON chain_live_rooms (profile_id, status)
    WHERE status IN ('live', 'scheduled');

-- 11. chain_dating_likes: discover exclusion filter
CREATE INDEX IF NOT EXISTS idx_p71_dating_likes_actor_target_created
    ON chain_dating_likes (actor_profile_id, target_profile_id, created_at DESC);

-- 12. chain_message_threads: inbox sort
CREATE INDEX IF NOT EXISTS idx_p71_threads_updated_desc
    ON chain_message_threads (updated_at DESC);
