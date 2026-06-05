-- CHAIN PHASE 9.5 OPTIMIZATIONS
-- Index improvements for slow queries and search

-- 1. Full-Text Search Optimization (if using ILIKE)
-- For better performance on search, we add trigram indexes
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS idx_chain_messages_body_trgm ON chain_messages USING gin (body gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_username_trgm ON chain_profiles USING gin (username gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_full_name_trgm ON chain_profiles USING gin (full_name gin_trgm_ops);

-- 2. Pagination & Sorting Improvements
CREATE INDEX IF NOT EXISTS idx_chain_posts_created_at_desc ON chain_posts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_status_posts_created_at_desc ON chain_status_posts (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_started_at_desc ON chain_call_sessions (started_at DESC);

-- 3. Deletion Performance (Profile Deletion cascade cleanup)
-- Ensure foreign keys have indexes if not already there
CREATE INDEX IF NOT EXISTS idx_chain_messages_sender_id ON chain_messages (sender_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_thread_members_profile_id ON chain_thread_members (profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_call_participants_profile_id ON chain_call_participants (profile_id);

-- 4. Status Performance
CREATE INDEX IF NOT EXISTS idx_chain_status_posts_profile_id ON chain_status_posts (profile_id, expires_at);

-- 5. Thread Performance
CREATE INDEX IF NOT EXISTS idx_chain_message_threads_updated_at ON chain_message_threads (updated_at DESC);
