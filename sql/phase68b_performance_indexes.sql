-- Phase 68B — Deep Performance Indexes
-- All statements are idempotent (IF NOT EXISTS).

-- ============================================================
-- SECTION 1: chain_profiles
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_profiles_id ON chain_profiles (id);
CREATE INDEX IF NOT EXISTS idx_68b_profiles_auth_user_id ON chain_profiles (auth_user_id);
CREATE INDEX IF NOT EXISTS idx_68b_profiles_username_lower ON chain_profiles (lower(username));
CREATE INDEX IF NOT EXISTS idx_68b_profiles_email_lower ON chain_profiles (lower(email));
CREATE INDEX IF NOT EXISTS idx_68b_profiles_is_online ON chain_profiles (is_online) WHERE is_online = true;
CREATE INDEX IF NOT EXISTS idx_68b_profiles_created_at ON chain_profiles (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_profiles_location ON chain_profiles (current_location);

-- ============================================================
-- SECTION 2: chain_follows
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_follows_follower_following ON chain_follows (follower_profile_id, following_profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_follows_following_follower ON chain_follows (following_profile_id, follower_profile_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_68b_follows_unique_pair ON chain_follows (follower_profile_id, following_profile_id);

-- ============================================================
-- SECTION 3: chain_notifications
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_notif_recipient_unread ON chain_notifications (recipient_profile_id, is_read) WHERE is_read = false AND deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_68b_notif_recipient_created ON chain_notifications (recipient_profile_id, created_at DESC);

-- ============================================================
-- SECTION 4: chain_messages
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_messages_thread_created ON chain_messages (thread_id, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_68b_messages_sender_created ON chain_messages (sender_profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_messages_delivery_state ON chain_messages (delivery_state);

-- ============================================================
-- SECTION 5: chain_thread_members
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_thread_members_thread_profile ON chain_thread_members (thread_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_thread_members_profile_thread ON chain_thread_members (profile_id, thread_id);

-- ============================================================
-- SECTION 6: chain_call_sessions
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_calls_caller_started ON chain_call_sessions (caller_profile_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_calls_receiver_started ON chain_call_sessions (receiver_profile_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_calls_status ON chain_call_sessions (status);
CREATE INDEX IF NOT EXISTS idx_68b_calls_created_at ON chain_call_sessions (created_at DESC);

-- ============================================================
-- SECTION 7: chain_wallet_transactions
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_wallet_tx_wallet_created ON chain_wallet_transactions (wallet_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_wallet_tx_status ON chain_wallet_transactions (status);

-- ============================================================
-- SECTION 8: marketplace tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_marketplace_seller ON chain_marketplace_items (seller_profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_marketplace_category ON chain_marketplace_items (category);
CREATE INDEX IF NOT EXISTS idx_68b_marketplace_created ON chain_marketplace_items (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_marketplace_status ON chain_marketplace_items (status);

-- ============================================================
-- SECTION 9: dating tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_dating_profiles_profile ON chain_dating_profiles (profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_dating_likes_target ON chain_dating_likes (target_profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_dating_matches_pair ON chain_dating_matches (profile_id_1, profile_id_2);

-- ============================================================
-- SECTION 10: creator tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_creator_profile ON chain_creator_subscriptions (creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_creator_created ON chain_creator_earnings (created_at DESC);

-- ============================================================
-- SECTION 11: live tables
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_live_host ON chain_live_rooms (host_profile_id);
CREATE INDEX IF NOT EXISTS idx_68b_live_status ON chain_live_rooms (status) WHERE status = 'live';
CREATE INDEX IF NOT EXISTS idx_68b_live_category ON chain_live_rooms (category);
CREATE INDEX IF NOT EXISTS idx_68b_live_viewers ON chain_live_rooms (viewer_count DESC);

-- ============================================================
-- SECTION 12: chain_posts
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_posts_profile_created ON chain_posts (profile_id, created_at DESC);

-- ============================================================
-- SECTION 13: chain_reels
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_reels_profile_created ON chain_reels (profile_id, created_at DESC);

-- ============================================================
-- SECTION 14: chain_message_threads
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_68b_threads_updated ON chain_message_threads (updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_68b_threads_created_by ON chain_message_threads (created_by_profile_id);
