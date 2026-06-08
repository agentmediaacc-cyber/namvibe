-- Phase 39: Real-Time Messaging Engine
-- All migrations are safe and idempotent

-- 1. Online Presence table
CREATE TABLE IF NOT EXISTS chain_online_presence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'offline',
    last_seen TIMESTAMPTZ DEFAULT now(),
    device_type VARCHAR(50) DEFAULT NULL,
    socket_id VARCHAR(255) DEFAULT NULL,
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_presence_profile_id ON chain_online_presence(profile_id);
CREATE INDEX IF NOT EXISTS idx_presence_status ON chain_online_presence(status);
CREATE INDEX IF NOT EXISTS idx_presence_updated ON chain_online_presence(updated_at);

-- Add unique constraint on profile_id if not present (for ON CONFLICT upsert)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'chain_online_presence'::regclass
          AND conname = 'chain_online_presence_profile_id_key'
    ) THEN
        ALTER TABLE chain_online_presence ADD UNIQUE (profile_id);
    END IF;
END $$;

-- 2. Message Reactions table
CREATE TABLE IF NOT EXISTS chain_message_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    reaction VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, profile_id)
);
CREATE INDEX IF NOT EXISTS idx_reactions_message_id ON chain_message_reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_reactions_profile_id ON chain_message_reactions(profile_id);

-- 3. Message Edits table
CREATE TABLE IF NOT EXISTS chain_message_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    editor_profile_id UUID NOT NULL,
    old_body TEXT,
    new_body TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_edits_message_id ON chain_message_edits(message_id);

-- 4. Add reply_to_message_id to chain_messages
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_messages' AND column_name = 'reply_to_message_id'
    ) THEN
        ALTER TABLE chain_messages ADD COLUMN reply_to_message_id UUID DEFAULT NULL;
    END IF;
END $$;

-- 5. Add deleted_at and deleted_for_everyone to chain_messages
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_messages' AND column_name = 'deleted_at'
    ) THEN
        ALTER TABLE chain_messages ADD COLUMN deleted_at TIMESTAMPTZ DEFAULT NULL;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_messages' AND column_name = 'deleted_for_everyone'
    ) THEN
        ALTER TABLE chain_messages ADD COLUMN deleted_for_everyone BOOLEAN DEFAULT FALSE;
    END IF;
END $$;

-- 6. Add voice_duration_seconds if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_messages' AND column_name = 'voice_duration_seconds'
    ) THEN
        ALTER TABLE chain_messages ADD COLUMN voice_duration_seconds INTEGER DEFAULT NULL;
    END IF;
END $$;

-- 7. Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_messages_reply_to ON chain_messages(reply_to_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_deleted ON chain_messages(deleted_at);
CREATE INDEX IF NOT EXISTS idx_messages_type ON chain_messages(message_type);
