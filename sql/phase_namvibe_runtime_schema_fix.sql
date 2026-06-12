ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_size_bytes BIGINT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_size_bytes BIGINT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_mime_type TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_mime_type TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_storage_bucket TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_storage_bucket TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_storage_path TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_storage_path TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_updated_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_updated_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS photo_url TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS thumbnail_url TEXT;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS followers_count BIGINT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS following_count BIGINT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT TRUE;
