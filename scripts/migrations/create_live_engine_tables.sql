-- Live Streaming Engine Phase 6 Migration (FIXED: UUID types)
-- Run after verifying chain_live_rooms exists

-- chain_live_chat_messages for the unified chat system (separate from chain_live_comments)
CREATE TABLE IF NOT EXISTS chain_live_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    display_name VARCHAR(128) DEFAULT '',
    body TEXT NOT NULL,
    is_pinned BOOLEAN NOT NULL DEFAULT FALSE,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_chat_room ON chain_live_chat_messages(room_id, created_at DESC);

-- chain_live_reactions for emoji reactions in live rooms
CREATE TABLE IF NOT EXISTS chain_live_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    reaction_type VARCHAR(32) NOT NULL DEFAULT 'heart',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_reactions_room ON chain_live_reactions(room_id, created_at DESC);

-- chain_live_guest_requests (if not already created by phase29)
CREATE TABLE IF NOT EXISTS chain_live_guest_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    note TEXT DEFAULT '',
    updated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_guest_requests_room ON chain_live_guest_requests(room_id, status);

-- chain_live_gifts — gift transactions (if not already created)
CREATE TABLE IF NOT EXISTS chain_live_gifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    sender_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    host_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    gift_name VARCHAR(64) DEFAULT 'Gift',
    gift_icon VARCHAR(32) DEFAULT '🎁',
    coins INTEGER NOT NULL DEFAULT 0,
    wallet_transaction_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_gifts_room ON chain_live_gifts(room_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_live_gifts_sender ON chain_live_gifts(sender_profile_id);

-- chain_live_moderation_actions (if not already created)
CREATE TABLE IF NOT EXISTS chain_live_moderation_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES chain_live_rooms(id) ON DELETE CASCADE,
    moderator_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    target_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    action_type VARCHAR(32) NOT NULL,
    reason TEXT DEFAULT '',
    duration_minutes INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_live_moderation_room ON chain_live_moderation_actions(room_id, created_at DESC);

-- Add columns to chain_live_rooms if missing
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_live_rooms' AND column_name = 'trending_score') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN trending_score REAL DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_live_rooms' AND column_name = 'peak_viewer_count') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN peak_viewer_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_live_rooms' AND column_name = 'reaction_count') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN reaction_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_live_rooms' AND column_name = 'chat_message_count') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN chat_message_count INTEGER DEFAULT 0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_live_rooms' AND column_name = 'replay_url') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN replay_url TEXT DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_live_rooms' AND column_name = 'ended_at') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN ended_at TIMESTAMPTZ;
    END IF;
END $$;
