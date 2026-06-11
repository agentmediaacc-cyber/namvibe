-- Final media storage metadata schema.
-- Heavy files live in Supabase Storage. Neon stores URLs, bucket/path, MIME,
-- size, type, text, status, visibility, counts, and relationships only.

ALTER TABLE IF EXISTS chain_profiles
    ADD COLUMN IF NOT EXISTS avatar_bucket text,
    ADD COLUMN IF NOT EXISTS avatar_path text,
    ADD COLUMN IF NOT EXISTS avatar_mime_type text,
    ADD COLUMN IF NOT EXISTS avatar_size_bytes bigint,
    ADD COLUMN IF NOT EXISTS cover_bucket text,
    ADD COLUMN IF NOT EXISTS cover_path text,
    ADD COLUMN IF NOT EXISTS cover_mime_type text,
    ADD COLUMN IF NOT EXISTS cover_size_bytes bigint,
    ADD COLUMN IF NOT EXISTS storage_bucket text,
    ADD COLUMN IF NOT EXISTS storage_path text;

ALTER TABLE IF EXISTS chain_posts
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS media_type text;

ALTER TABLE IF EXISTS chain_reels
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS media_type text;

ALTER TABLE IF EXISTS chain_stories
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS media_type text;

ALTER TABLE IF EXISTS chain_status_posts
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS media_type text;

ALTER TABLE IF EXISTS chain_messages
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS storage_bucket text,
    ADD COLUMN IF NOT EXISTS storage_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint;

ALTER TABLE IF EXISTS chain_live_rooms
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS cover_bucket text,
    ADD COLUMN IF NOT EXISTS cover_path text,
    ADD COLUMN IF NOT EXISTS cover_mime_type text,
    ADD COLUMN IF NOT EXISTS cover_size_bytes bigint;

ALTER TABLE IF EXISTS chain_marketplace_items
    ADD COLUMN IF NOT EXISTS media_bucket text,
    ADD COLUMN IF NOT EXISTS media_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS cover_bucket text,
    ADD COLUMN IF NOT EXISTS cover_path text,
    ADD COLUMN IF NOT EXISTS cover_mime_type text,
    ADD COLUMN IF NOT EXISTS cover_size_bytes bigint;

ALTER TABLE IF EXISTS chain_media_uploads
    ADD COLUMN IF NOT EXISTS media_url text,
    ADD COLUMN IF NOT EXISTS public_url text,
    ADD COLUMN IF NOT EXISTS storage_bucket text,
    ADD COLUMN IF NOT EXISTS storage_path text,
    ADD COLUMN IF NOT EXISTS mime_type text,
    ADD COLUMN IF NOT EXISTS file_size bigint,
    ADD COLUMN IF NOT EXISTS size_bytes bigint,
    ADD COLUMN IF NOT EXISTS media_type text,
    ADD COLUMN IF NOT EXISTS upload_type text,
    ADD COLUMN IF NOT EXISTS original_filename text;
