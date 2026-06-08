-- Stabilization: content routes and homepage speed indexes.
-- Safe/idempotent migration for PostgreSQL/Neon.

CREATE INDEX IF NOT EXISTS idx_chain_posts_created_at_desc
ON chain_posts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_posts_deleted_created
ON chain_posts(deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_reels_deleted_created
ON chain_reels(deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_stories_deleted_created
ON chain_stories(deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_status_posts_expires_created
ON chain_status_posts(expires_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_status_created
ON chain_live_rooms(status, is_live, deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_profiles_creator_created
ON chain_profiles(is_creator, deleted_at, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_profiles_username_lower
ON chain_profiles(LOWER(username));

CREATE INDEX IF NOT EXISTS idx_chain_hashtags_tag
ON chain_hashtags(tag);

CREATE INDEX IF NOT EXISTS idx_chain_content_hashtags_content
ON chain_content_hashtags(content_id);
