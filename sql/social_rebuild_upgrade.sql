-- CHAIN Social Rebuild Upgrade
-- Non-destructive schema evolution for advanced social features

-- Advanced Profile Metadata
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS parent_profile_id uuid REFERENCES chain_profiles(id);
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_page boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_visibility text DEFAULT 'public'; -- public, private, premium
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_audio_calls boolean DEFAULT true;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_video_calls boolean DEFAULT true;

-- Group Messaging Support
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS thread_name text;
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS thread_avatar_url text;

-- Page Likes (Distinct from follows)
CREATE TABLE IF NOT EXISTS chain_page_likes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    page_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, page_id)
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_page_likes_page_id ON chain_page_likes(page_id);
CREATE INDEX IF NOT EXISTS idx_profiles_parent_id ON chain_profiles(parent_profile_id);
