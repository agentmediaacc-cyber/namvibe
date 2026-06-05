-- CHAIN PHASE 9 SCHEMA UPDATES

-- Messages Extension
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS parent_message_id uuid REFERENCES chain_messages(id) ON DELETE SET NULL;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_forwarded boolean DEFAULT false;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS status_id uuid; -- Reference to status if it's a status reply
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS seen_at timestamptz;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivery_status text DEFAULT 'sent'; -- sent, delivered, seen

-- Thread Members Extension
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS is_pinned boolean DEFAULT false;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS is_archived boolean DEFAULT false;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS last_read_message_id uuid;

-- Message Reactions
CREATE TABLE IF NOT EXISTS chain_message_reactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid REFERENCES chain_messages(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reaction_type text NOT NULL, -- emoji or sticker id
    created_at timestamptz DEFAULT now(),
    UNIQUE (message_id, profile_id, reaction_type)
);

-- Message Deletions (Delete for me)
CREATE TABLE IF NOT EXISTS chain_message_deletions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id uuid REFERENCES chain_messages(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    deleted_at timestamptz DEFAULT now(),
    UNIQUE (message_id, profile_id)
);

-- Status Upgrades (Ensure table exists and has needed columns)
CREATE TABLE IF NOT EXISTS chain_status_posts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    caption text,
    media_url text,
    media_type text DEFAULT 'image', -- image, video, text
    storage_bucket text,
    storage_path text,
    visibility text DEFAULT 'public', -- public, contacts, close_friends
    expires_at timestamptz DEFAULT (now() + interval '24 hours'),
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS media_type text DEFAULT 'image';
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS visibility text DEFAULT 'public';
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS expires_at timestamptz DEFAULT (now() + interval '24 hours');

CREATE TABLE IF NOT EXISTS chain_status_viewers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status_id uuid REFERENCES chain_status_posts(id) ON DELETE CASCADE,
    viewer_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    viewed_at timestamptz DEFAULT now(),
    UNIQUE (status_id, viewer_profile_id)
);

-- Calls Engine Extension
CREATE TABLE IF NOT EXISTS chain_call_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid REFERENCES chain_message_threads(id) ON DELETE SET NULL,
    caller_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    receiver_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE, -- For 1:1
    call_type text DEFAULT 'video', -- audio, video
    call_status text DEFAULT 'ringing', -- ringing, answered, missed, rejected, ended
    room_id text, -- Socket.IO room or WebRTC room
    started_at timestamptz DEFAULT now(),
    answered_at timestamptz,
    ended_at timestamptz,
    duration_seconds integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

ALTER TABLE chain_call_sessions ADD COLUMN IF NOT EXISTS room_id text;

CREATE TABLE IF NOT EXISTS chain_call_participants (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id uuid REFERENCES chain_call_sessions(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status text DEFAULT 'invited', -- invited, ringing, accepted, declined, left
    joined_at timestamptz,
    left_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id uuid REFERENCES chain_call_sessions(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    event_type text NOT NULL, -- offer, answer, ice-candidate, mute, camera-off
    payload jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);

-- Restricted Users
CREATE TABLE IF NOT EXISTS chain_restricted_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    restricter_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    restricted_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE (restricter_profile_id, restricted_profile_id)
);
