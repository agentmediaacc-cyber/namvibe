-- Phase 51: Performance optimization indexes.
-- Safe/idempotent migration for PostgreSQL/Neon.

CREATE INDEX IF NOT EXISTS idx_phase51_chain_posts_created_at
ON chain_posts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_phase51_chain_reels_created_at
ON chain_reels(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_phase51_chain_stories_created_at
ON chain_stories(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_phase51_chain_live_rooms_created_at
ON chain_live_rooms(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_phase51_chain_profiles_username
ON chain_profiles(username);
