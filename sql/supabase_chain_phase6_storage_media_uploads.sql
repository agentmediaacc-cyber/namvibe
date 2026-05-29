-- CHAIN Phase 6: Storage & Media Uploads
-- This migration adds the media tracking table and extends existing features with storage support.

-- Media tracking table
CREATE TABLE IF NOT EXISTS chain_media_uploads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    upload_type text NOT NULL, -- 'avatar', 'cover', 'marketplace_media', 'music_track', 'payment_proof', 'verification_doc', etc.
    bucket_name text NOT NULL,
    file_path text NOT NULL,
    public_url text,
    mime_type text,
    file_size integer,
    original_filename text,
    status text DEFAULT 'active', -- 'active', 'archived', 'deleted'
    created_at timestamptz DEFAULT now()
);

-- Index for performance
CREATE INDEX IF NOT EXISTS idx_chain_media_uploads_profile_id ON chain_media_uploads(profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_media_uploads_type ON chain_media_uploads(upload_type);

-- Extend chain_profiles for better avatar/cover management
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_profiles' AND COLUMN_NAME = 'avatar_upload_id') THEN
        ALTER TABLE chain_profiles ADD COLUMN avatar_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_profiles' AND COLUMN_NAME = 'cover_upload_id') THEN
        ALTER TABLE chain_profiles ADD COLUMN cover_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend marketplace for media tracking
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_marketplace_items' AND COLUMN_NAME = 'media_upload_id') THEN
        ALTER TABLE chain_marketplace_items ADD COLUMN media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_marketplace_items' AND COLUMN_NAME = 'cover_upload_id') THEN
        ALTER TABLE chain_marketplace_items ADD COLUMN cover_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend music albums/tracks
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_music_albums' AND COLUMN_NAME = 'cover_upload_id') THEN
        ALTER TABLE chain_music_albums ADD COLUMN cover_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_music_tracks' AND COLUMN_NAME = 'audio_upload_id') THEN
        ALTER TABLE chain_music_tracks ADD COLUMN audio_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend wallet top-ups for proof tracking
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_wallet_topups' AND COLUMN_NAME = 'proof_upload_id') THEN
        ALTER TABLE chain_wallet_topups ADD COLUMN proof_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend user verifications
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_user_verifications' AND COLUMN_NAME = 'selfie_upload_id') THEN
        ALTER TABLE chain_user_verifications ADD COLUMN selfie_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_user_verifications' AND COLUMN_NAME = 'id_document_upload_id') THEN
        ALTER TABLE chain_user_verifications ADD COLUMN id_document_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend status posts for media tracking
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_status_posts' AND COLUMN_NAME = 'media_upload_id') THEN
        ALTER TABLE chain_status_posts ADD COLUMN media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend messages for media tracking
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_messages' AND COLUMN_NAME = 'media_upload_id') THEN
        ALTER TABLE chain_messages ADD COLUMN media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Extend live rooms for cover and music
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'live_cover_upload_id') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN live_cover_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'background_music_upload_id') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN background_music_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Additional indexes for new columns
CREATE INDEX IF NOT EXISTS idx_chain_status_posts_media_upload ON chain_status_posts(media_upload_id);
CREATE INDEX IF NOT EXISTS idx_chain_messages_media_upload ON chain_messages(media_upload_id);
CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_cover_upload ON chain_live_rooms(live_cover_upload_id);
CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_music_upload ON chain_live_rooms(background_music_upload_id);

