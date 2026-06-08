CREATE TABLE IF NOT EXISTS chain_message_threads (
    id UUID PRIMARY KEY,
    created_by_profile_id UUID,
    thread_type TEXT DEFAULT 'direct',
    thread_name TEXT,
    thread_avatar_url TEXT,
    group_id UUID,
    folder_type TEXT DEFAULT 'primary',
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_thread_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    role TEXT DEFAULT 'member',
    muted BOOLEAN DEFAULT FALSE,
    is_pinned BOOLEAN DEFAULT FALSE,
    is_archived BOOLEAN DEFAULT FALSE,
    last_read_at TIMESTAMPTZ,
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(thread_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_messages (
    id UUID PRIMARY KEY,
    thread_id UUID NOT NULL,
    sender_profile_id UUID NOT NULL,
    body TEXT,
    message_type TEXT DEFAULT 'text',
    media_url TEXT,
    media_type TEXT,
    storage_bucket TEXT,
    storage_path TEXT,
    client_event_id TEXT,
    parent_message_id UUID,
    is_forwarded BOOLEAN DEFAULT FALSE,
    delivery_status TEXT DEFAULT 'sent',
    delivered_at TIMESTAMPTZ,
    seen_at TIMESTAMPTZ,
    read_at TIMESTAMPTZ,
    is_seen BOOLEAN DEFAULT FALSE,
    edited_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    reaction_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, profile_id, reaction_type)
);

CREATE TABLE IF NOT EXISTS chain_message_stars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_message_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    editor_profile_id UUID NOT NULL,
    old_body TEXT,
    new_body TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_deletions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    delete_scope TEXT DEFAULT 'me',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_message_forwards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id UUID NOT NULL,
    forwarded_message_id UUID,
    from_profile_id UUID NOT NULL,
    target_thread_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID,
    attachment_type TEXT DEFAULT 'file',
    file_name TEXT,
    media_url TEXT,
    storage_bucket TEXT,
    storage_path TEXT,
    mime_type TEXT,
    file_size BIGINT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_voice_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    audio_url TEXT,
    storage_bucket TEXT,
    storage_path TEXT,
    duration_seconds NUMERIC DEFAULT 0,
    waveform JSONB DEFAULT '[]'::jsonb,
    mime_type TEXT,
    file_size BIGINT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_reads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    thread_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    delivered_at TIMESTAMPTZ,
    seen_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(message_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_groups (
    id UUID PRIMARY KEY,
    owner_profile_id UUID NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    visibility TEXT DEFAULT 'public',
    access_type TEXT DEFAULT 'public',
    join_fee NUMERIC DEFAULT 0,
    premium_only BOOLEAN DEFAULT FALSE,
    invite_code TEXT UNIQUE,
    allow_typing BOOLEAN DEFAULT TRUE,
    allow_replies BOOLEAN DEFAULT TRUE,
    allow_comments BOOLEAN DEFAULT TRUE,
    allow_adverts BOOLEAN DEFAULT FALSE,
    allow_group_calls BOOLEAN DEFAULT TRUE,
    allow_member_invites BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'active',
    joined_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(group_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_group_join_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(group_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_group_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    inviter_profile_id UUID,
    invite_code TEXT UNIQUE,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    post_type TEXT DEFAULT 'message',
    body TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_sessions (
    id UUID PRIMARY KEY,
    conversation_id UUID,
    caller_profile_id UUID NOT NULL,
    receiver_profile_id UUID,
    call_type TEXT DEFAULT 'audio',
    call_status TEXT DEFAULT 'ringing',
    room_id TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    answered_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_seconds INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS chain_call_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    status TEXT DEFAULT 'invited',
    joined_at TIMESTAMPTZ,
    left_at TIMESTAMPTZ,
    muted BOOLEAN DEFAULT FALSE,
    camera_enabled BOOLEAN DEFAULT TRUE,
    screen_sharing BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(call_session_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_call_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL,
    profile_id UUID,
    event_type TEXT NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID,
    host_profile_id UUID,
    title TEXT,
    host_name TEXT,
    status TEXT DEFAULT 'live',
    is_live BOOLEAN DEFAULT TRUE,
    viewer_count INTEGER DEFAULT 0,
    allow_comments BOOLEAN DEFAULT TRUE,
    allow_gifts BOOLEAN DEFAULT TRUE,
    access_type TEXT DEFAULT 'public',
    created_at TIMESTAMPTZ DEFAULT now(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_live_viewers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID,
    display_name TEXT,
    joined_at TIMESTAMPTZ DEFAULT now(),
    left_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_live_comments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID,
    display_name TEXT,
    body TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_gifts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    sender_profile_id UUID,
    gift_name TEXT,
    gift_icon TEXT,
    amount NUMERIC DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_gift_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    gift_type TEXT,
    gift_name TEXT,
    gift_icon TEXT,
    coin_price NUMERIC DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_earnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    source_type TEXT,
    source_id UUID,
    amount NUMERIC DEFAULT 0,
    currency TEXT DEFAULT 'coins',
    status TEXT DEFAULT 'available',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    subscriber_profile_id UUID NOT NULL,
    tier TEXT DEFAULT 'premium',
    status TEXT DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_creator_supporters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    supporter_profile_id UUID NOT NULL,
    total_amount NUMERIC DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(creator_profile_id, supporter_profile_id)
);

CREATE TABLE IF NOT EXISTS chain_verification_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    request_type TEXT DEFAULT 'creator',
    status TEXT DEFAULT 'pending',
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivery_status TEXT DEFAULT 'sent';
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ;
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS group_id UUID;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS allow_comments BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS allow_gifts BOOLEAN DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_chain_messages_thread_id ON chain_messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_chain_messages_sender_profile_id ON chain_messages(sender_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_thread_members_thread_profile ON chain_thread_members(thread_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_participants ON chain_call_sessions(caller_profile_id, receiver_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_live_rooms_status ON chain_live_rooms(status, is_live);
CREATE INDEX IF NOT EXISTS idx_chain_group_members_group_profile ON chain_group_members(group_id, profile_id);
