-- Phase 130: Optimize profile and contacts queries
-- Run: psql $DATABASE_URL -f migrations/003_profile_contacts_indexes.sql

-- Index for profile lookups by username (profile_routes.py)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_username_deleted
    ON chain_profiles (username, deleted_at)
    WHERE deleted_at IS NULL;

-- Index for profile lookups by auth_user_id
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_profiles_auth_user_deleted
    ON chain_profiles (auth_user_id, deleted_at)
    WHERE deleted_at IS NULL;

-- Index for contacts route - friends lookup
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_friends_status_profile1_profile2
    ON chain_friends (status, profile_id_1, profile_id_2)
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_friends_status_profile2_profile1
    ON chain_friends (status, profile_id_2, profile_id_1)
    WHERE deleted_at IS NULL;

-- Index for contacts search
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_friends_search
    ON chain_friends (profile_id_1, profile_id_2, status, deleted_at)
    WHERE deleted_at IS NULL;

-- Indexes for discover profiles (dating_service.py)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dating_profiles_mode_trust
    ON chain_dating_profiles (dating_mode_on, trust_score DESC, updated_at DESC);

-- Index for dating blocks
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dating_blocks_blocker
    ON chain_dating_blocks (blocker_profile_id, blocked_profile_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dating_blocks_blocked
    ON chain_dating_blocks (blocked_profile_id, blocker_profile_id);

-- Index for dating preferences
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dating_preferences_profile
    ON chain_dating_preferences (profile_id);

-- Index for presence lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_presence_profile
    ON chain_presence (profile_id, status);

-- Index for wallet lookups
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wallets_profile
    ON chain_wallets (profile_id);

-- Index for creator tools
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_creator_tools_profile
    ON chain_creator_tools (profile_id);

-- Index for profile stats (followers/following counts)
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_follows_follower
    ON chain_follows (following_profile_id, deleted_at)
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_follows_following
    ON chain_follows (follower_profile_id, deleted_at)
    WHERE deleted_at IS NULL;