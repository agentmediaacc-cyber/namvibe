-- Phase 67 — Enterprise Performance & Production Hardening
-- Missing indexes for frequently queried columns.
-- All statements are idempotent (IF NOT EXISTS).

-- ============================================================
-- SECTION 1: chain_profiles
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_profiles_created_at
    ON chain_profiles (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_profiles_username_lookup
    ON chain_profiles (username);
CREATE INDEX IF NOT EXISTS idx_p67_profiles_email_lookup
    ON chain_profiles (email);

-- ============================================================
-- SECTION 2: chain_posts
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_posts_profile_created
    ON chain_posts (profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_posts_hashtag_lookup
    ON chain_posts USING gin (to_tsvector('simple', coalesce(content, '')));

-- ============================================================
-- SECTION 3: chain_reels
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_reels_profile_created
    ON chain_reels (profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_reels_view_count
    ON chain_reels (view_count DESC NULLS LAST);

-- ============================================================
-- SECTION 4: chain_messages
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_messages_conversation_created
    ON chain_messages (conversation_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_p67_messages_sender_recipient
    ON chain_messages (sender_profile_id, created_at DESC);

-- ============================================================
-- SECTION 5: chain_notifications
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_notifications_profile_created
    ON chain_notifications (profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_notifications_type_profile
    ON chain_notifications (type, profile_id);
CREATE INDEX IF NOT EXISTS idx_p67_notifications_read_status
    ON chain_notifications (profile_id, is_read) WHERE is_read = false;

-- ============================================================
-- SECTION 6: chain_wallet_transactions / chain_wallets
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_wallet_tx_wallet_created
    ON chain_wallet_transactions (wallet_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_wallet_tx_type
    ON chain_wallet_transactions (transaction_type);
CREATE INDEX IF NOT EXISTS idx_p67_wallet_ledger_profile
    ON chain_wallet_ledger_entries (profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_wallet_idempotency_key
    ON chain_wallet_idempotency_keys (idempotency_key);

-- ============================================================
-- SECTION 7: chain_marketplace tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_marketplace_items_seller
    ON chain_marketplace_items (seller_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_marketplace_items_status
    ON chain_marketplace_items (status);
CREATE INDEX IF NOT EXISTS idx_p67_marketplace_items_category
    ON chain_marketplace_items (category);
CREATE INDEX IF NOT EXISTS idx_p67_marketplace_orders_buyer
    ON chain_marketplace_orders (buyer_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_marketplace_orders_seller
    ON chain_marketplace_orders (seller_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_marketplace_reviews_item
    ON chain_marketplace_reviews (item_id, created_at DESC);

-- ============================================================
-- SECTION 8: chain_dating tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_dating_profiles_profile
    ON chain_dating_profiles (profile_id);
CREATE INDEX IF NOT EXISTS idx_p67_dating_profiles_gender
    ON chain_dating_profiles (gender);
CREATE INDEX IF NOT EXISTS idx_p67_dating_likes_sender
    ON chain_dating_likes (sender_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_dating_likes_recipient
    ON chain_dating_likes (recipient_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_dating_matches_pair
    ON chain_dating_matches (profile_id_1, profile_id_2);
CREATE INDEX IF NOT EXISTS idx_p67_dating_matches_active
    ON chain_dating_matches (status) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS idx_p67_dating_reports_reporter
    ON chain_dating_reports (reporter_profile_id, created_at DESC);

-- ============================================================
-- SECTION 9: chain_live tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_live_rooms_host_status
    ON chain_live_rooms (host_profile_id, status);
CREATE INDEX IF NOT EXISTS idx_p67_live_rooms_active
    ON chain_live_rooms (status) WHERE status = 'live';
CREATE INDEX IF NOT EXISTS idx_p67_live_participants_room
    ON chain_live_participants (room_id, joined_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_live_gifts_room
    ON chain_live_gifts (room_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_live_battles_room
    ON chain_live_battles (room_id, started_at DESC);

-- ============================================================
-- SECTION 10: chain_follows
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_follows_follower
    ON chain_follows (follower_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_follows_following
    ON chain_follows (following_profile_id, created_at DESC);

-- ============================================================
-- SECTION 11: chain_conversations
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_conversations_updated
    ON chain_conversations (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_conversation_members_profile
    ON chain_conversation_members (profile_id, conversation_id);

-- ============================================================
-- SECTION 12: chain_subscriptions
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_subscriptions_subscriber
    ON chain_subscriptions (subscriber_profile_id, status);
CREATE INDEX IF NOT EXISTS idx_p67_subscriptions_creator
    ON chain_subscriptions (creator_profile_id, status);

-- ============================================================
-- SECTION 13: chain_analytics_events
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_analytics_event_type
    ON chain_analytics_events (event_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_analytics_profile
    ON chain_analytics_events (profile_id, created_at DESC);

-- ============================================================
-- SECTION 14: chain_ai tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_ai_sessions_profile_type
    ON chain_ai_chat_sessions (profile_id, assistant_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_ai_suggestions_profile_applied
    ON chain_ai_suggestions (profile_id, was_applied, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_ai_moderation_log_created
    ON chain_ai_moderation_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_ai_feedback_rating
    ON chain_ai_feedback (assistant_type, rating);

-- ============================================================
-- SECTION 15: chain_blocks / chain_reports
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_p67_blocks_blocker
    ON chain_blocks (blocker_profile_id, blocked_profile_id);
CREATE INDEX IF NOT EXISTS idx_p67_reports_reporter
    ON chain_reports (reporter_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p67_reports_status
    ON chain_reports (status, created_at DESC);
