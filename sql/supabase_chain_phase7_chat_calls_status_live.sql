-- CHAIN Phase 7: Chat, Calls, Status, and Live Media Controls
-- This migration adds tables for advanced real-time communication and enhances live rooms.

-- Conversations table (upgraded version)
CREATE TABLE IF NOT EXISTS chain_conversations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_type text DEFAULT 'direct', -- 'direct', 'group', 'channel'
    title text,
    created_by uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    last_message text,
    last_message_at timestamptz,
    created_at timestamptz DEFAULT now()
);

-- Conversation members tracking
CREATE TABLE IF NOT EXISTS chain_conversation_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES chain_conversations(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    role text DEFAULT 'member', -- 'member', 'admin', 'owner'
    joined_at timestamptz DEFAULT now(),
    muted boolean DEFAULT false,
    blocked boolean DEFAULT false,
    UNIQUE(conversation_id, profile_id)
);

-- Messages table (upgraded version)
CREATE TABLE IF NOT EXISTS chain_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES chain_conversations(id) ON DELETE CASCADE,
    sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    message_type text DEFAULT 'text', -- 'text', 'image', 'video', 'audio', 'file', 'call'
    body text,
    media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL,
    media_url text,
    mime_type text,
    reply_to_message_id uuid REFERENCES chain_messages(id) ON DELETE SET NULL,
    is_read boolean DEFAULT false,
    is_deleted boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chain_messages_convo ON chain_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chain_messages_sender ON chain_messages(sender_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_messages_created ON chain_messages(created_at);

-- Call sessions tracking
CREATE TABLE IF NOT EXISTS chain_call_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES chain_conversations(id) ON DELETE SET NULL,
    caller_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    receiver_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    call_type text NOT NULL, -- 'audio', 'video'
    call_status text DEFAULT 'ringing', -- 'ringing', 'answered', 'missed', 'rejected', 'ended'
    started_at timestamptz DEFAULT now(),
    answered_at timestamptz,
    ended_at timestamptz,
    duration_seconds integer DEFAULT 0
);

-- Status/Stories table
CREATE TABLE IF NOT EXISTS chain_status_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status_type text DEFAULT 'story', -- 'story', 'mood', 'announcement'
    caption text,
    media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL,
    media_url text,
    music_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL,
    music_url text,
    visibility text DEFAULT 'public', -- 'public', 'followers', 'private'
    expires_at timestamptz DEFAULT now() + interval '24 hours',
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_status_profile ON chain_status_posts(profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_status_expires ON chain_status_posts(expires_at);

-- Extend chain_live_rooms with media controls and settings
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'stream_mode') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN stream_mode text DEFAULT 'camera';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'allow_camera') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN allow_camera boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'allow_microphone') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN allow_microphone boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'allow_screen_share') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN allow_screen_share boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'allow_youtube_embed') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN allow_youtube_embed boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'allow_mp3_music') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN allow_mp3_music boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'background_music_url') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN background_music_url text;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'background_music_upload_id') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN background_music_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'live_cover_upload_id') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN live_cover_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'cohost_enabled') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN cohost_enabled boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'gifts_enabled') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN gifts_enabled boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'comments_enabled') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN comments_enabled boolean DEFAULT true;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'private_mode') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN private_mode boolean DEFAULT false;
    END IF;
END $$;
