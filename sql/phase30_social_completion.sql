-- Phase 30 WhatsApp/TikTok live/creator completion schema.
-- Safe to re-run: only IF NOT EXISTS DDL is used.

CREATE TABLE IF NOT EXISTS chain_message_forwards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_message_id UUID,
    forwarded_message_id UUID,
    from_thread_id UUID,
    to_thread_id UUID,
    profile_id UUID,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_reactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    reaction_type TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_stars (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_edits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    editor_profile_id UUID,
    old_body TEXT,
    new_body TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_deletions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    delete_scope TEXT DEFAULT 'me',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_voice_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    audio_url TEXT,
    duration_seconds NUMERIC DEFAULT 0,
    waveform JSONB DEFAULT '[]'::jsonb,
    mime_type TEXT,
    file_size BIGINT,
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
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID,
    caller_profile_id UUID,
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
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL,
    profile_id UUID,
    event_type TEXT NOT NULL,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_profile_id UUID NOT NULL,
    name TEXT NOT NULL,
    visibility TEXT DEFAULT 'public',
    access_type TEXT DEFAULT 'public',
    join_fee NUMERIC DEFAULT 0,
    premium_only BOOLEAN DEFAULT FALSE,
    invite_code TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    role TEXT DEFAULT 'member',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_join_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    invite_code TEXT NOT NULL,
    created_by_profile_id UUID,
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

CREATE TABLE IF NOT EXISTS chain_creator_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    subscriber_profile_id UUID NOT NULL,
    tier TEXT DEFAULT 'premium',
    status TEXT DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_creator_earnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    source_type TEXT,
    source_id UUID,
    amount NUMERIC DEFAULT 0,
    currency TEXT DEFAULT 'coins',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_supporters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    supporter_profile_id UUID NOT NULL,
    total_amount NUMERIC DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now()
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

CREATE TABLE IF NOT EXISTS chain_message_pins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    thread_id UUID,
    profile_id UUID NOT NULL,
    pinned BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    body TEXT,
    attachment_payload JSONB DEFAULT '{}'::jsonb,
    voice_note_payload JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_scheduled (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    sender_profile_id UUID NOT NULL,
    body TEXT,
    message_type TEXT DEFAULT 'text',
    scheduled_for TIMESTAMPTZ NOT NULL,
    status TEXT DEFAULT 'scheduled',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_wallpapers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    wallpaper_key TEXT,
    wallpaper_url TEXT,
    settings JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_shared_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    message_id UUID,
    profile_id UUID,
    item_type TEXT NOT NULL,
    title TEXT,
    url TEXT,
    mime_type TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_autodownload_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    wifi_photos BOOLEAN DEFAULT TRUE,
    wifi_videos BOOLEAN DEFAULT FALSE,
    wifi_documents BOOLEAN DEFAULT TRUE,
    mobile_photos BOOLEAN DEFAULT FALSE,
    mobile_videos BOOLEAN DEFAULT FALSE,
    mobile_documents BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_message_encryption_status (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    profile_id UUID,
    status TEXT DEFAULT 'transport_protected',
    provider TEXT DEFAULT 'chain',
    metadata JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_voice_note_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    audio_url TEXT,
    duration_seconds NUMERIC DEFAULT 0,
    waveform JSONB DEFAULT '[]'::jsonb,
    mime_type TEXT,
    file_size BIGINT,
    draft_state TEXT DEFAULT 'draft',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_voice_note_playback_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    playback_speed NUMERIC DEFAULT 1,
    played BOOLEAN DEFAULT FALSE,
    position_seconds NUMERIC DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_quality_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL,
    profile_id UUID,
    event_type TEXT NOT NULL,
    quality_score NUMERIC,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_recording_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    allow_recording BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_device_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    preferred_audio_input TEXT,
    preferred_audio_output TEXT,
    preferred_video_input TEXT,
    hd_enabled BOOLEAN DEFAULT TRUE,
    noise_suppression BOOLEAN DEFAULT TRUE,
    background_blur BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_call_waiting_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    call_session_id UUID NOT NULL,
    waiting_profile_id UUID NOT NULL,
    incoming_profile_id UUID,
    status TEXT DEFAULT 'waiting',
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    role TEXT NOT NULL,
    assigned_by_profile_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_announcements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    title TEXT,
    body TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_adverts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    title TEXT,
    body TEXT,
    media_url TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value NUMERIC DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_verification (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    status TEXT DEFAULT 'pending',
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_live_rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    room_id UUID,
    profile_id UUID NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_reels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    reel_id UUID,
    caption TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_group_marketplace_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price_coins NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_guest_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    status TEXT DEFAULT 'pending',
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_polls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    question TEXT NOT NULL,
    options JSONB DEFAULT '[]'::jsonb,
    votes JSONB DEFAULT '{}'::jsonb,
    status TEXT DEFAULT 'open',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_battles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    challenger_room_id UUID,
    host_profile_id UUID,
    challenger_profile_id UUID,
    status TEXT DEFAULT 'invited',
    scores JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_moderation_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    moderator_profile_id UUID,
    target_profile_id UUID,
    action_type TEXT NOT NULL,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_replays (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID,
    replay_url TEXT,
    duration_seconds NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'ready',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_clips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    clip_url TEXT,
    start_seconds NUMERIC DEFAULT 0,
    duration_seconds NUMERIC DEFAULT 0,
    title TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_shopping_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    title TEXT NOT NULL,
    price_coins NUMERIC DEFAULT 0,
    url TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_leaderboard (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    score NUMERIC DEFAULT 0,
    rank INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_live_stream_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    webrtc_enabled BOOLEAN DEFAULT TRUE,
    rtmp_enabled BOOLEAN DEFAULT FALSE,
    rtmp_stream_key TEXT,
    turn_required BOOLEAN DEFAULT FALSE,
    settings JSONB DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_paid_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    post_id UUID,
    title TEXT,
    price_coins NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_premium_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    content_id UUID,
    content_type TEXT DEFAULT 'post',
    lock_type TEXT DEFAULT 'subscription',
    price_coins NUMERIC DEFAULT 0,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_payouts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    amount_coins NUMERIC DEFAULT 0,
    payout_method TEXT,
    status TEXT DEFAULT 'pending',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_gift_conversions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    supporter_profile_id UUID,
    gift_id UUID,
    coins NUMERIC DEFAULT 0,
    conversion_rate NUMERIC DEFAULT 1,
    status TEXT DEFAULT 'recorded',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_revenue_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    period_key TEXT NOT NULL,
    gross_coins NUMERIC DEFAULT 0,
    net_coins NUMERIC DEFAULT 0,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_sponsorships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    sponsor_name TEXT NOT NULL,
    status TEXT DEFAULT 'prospect',
    amount_coins NUMERIC DEFAULT 0,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    badge_key TEXT NOT NULL,
    label TEXT,
    awarded_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS chain_supporter_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    supporter_profile_id UUID NOT NULL,
    badge_key TEXT NOT NULL,
    label TEXT,
    awarded_at TIMESTAMPTZ DEFAULT now(),
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS chain_top_fans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    fan_profile_id UUID NOT NULL,
    score NUMERIC DEFAULT 0,
    rank INTEGER,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_rankings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID NOT NULL,
    category TEXT DEFAULT 'overall',
    score NUMERIC DEFAULT 0,
    rank INTEGER,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS parent_message_id UUID;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_forwarded BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS edited_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivery_status TEXT DEFAULT 'sent';
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivered_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS seen_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS read_at TIMESTAMPTZ;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_seen BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

ALTER TABLE chain_message_forwards ADD COLUMN IF NOT EXISTS source_message_id UUID;
ALTER TABLE chain_message_forwards ADD COLUMN IF NOT EXISTS forwarded_message_id UUID;
ALTER TABLE chain_message_forwards ADD COLUMN IF NOT EXISTS from_thread_id UUID;
ALTER TABLE chain_message_forwards ADD COLUMN IF NOT EXISTS to_thread_id UUID;
ALTER TABLE chain_message_forwards ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE chain_message_forwards ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();

ALTER TABLE chain_message_voice_notes ADD COLUMN IF NOT EXISTS playback_speed NUMERIC DEFAULT 1;
ALTER TABLE chain_message_voice_notes ADD COLUMN IF NOT EXISTS played BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_message_voice_notes ADD COLUMN IF NOT EXISTS draft_state TEXT;
ALTER TABLE chain_message_attachments ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}'::jsonb;

ALTER TABLE chain_call_sessions ADD COLUMN IF NOT EXISTS is_group_call BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_call_sessions ADD COLUMN IF NOT EXISTS parent_call_session_id UUID;
ALTER TABLE chain_call_sessions ADD COLUMN IF NOT EXISTS call_quality TEXT DEFAULT 'auto';
ALTER TABLE chain_call_sessions ADD COLUMN IF NOT EXISTS screen_share_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_call_sessions ADD COLUMN IF NOT EXISTS reconnect_state TEXT;

ALTER TABLE chain_groups ADD COLUMN IF NOT EXISTS paid_access BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_groups ADD COLUMN IF NOT EXISTS premium_only BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_groups ADD COLUMN IF NOT EXISTS marketplace_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_groups ADD COLUMN IF NOT EXISTS reels_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_groups ADD COLUMN IF NOT EXISTS live_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_groups ADD COLUMN IF NOT EXISTS verification_status TEXT DEFAULT 'none';

ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS webrtc_room_id TEXT;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS rtmp_stream_key TEXT;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS allow_guest_requests BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS allow_polls BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS replay_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS shopping_enabled BOOLEAN DEFAULT FALSE;

ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS price_coins NUMERIC DEFAULT 0;
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_p30_message_pins_message_id ON chain_message_pins(message_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_pins_thread_id ON chain_message_pins(thread_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_drafts_thread_profile ON chain_message_drafts(thread_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_scheduled_thread ON chain_message_scheduled(thread_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_scheduled_created ON chain_message_scheduled(created_at);
CREATE INDEX IF NOT EXISTS idx_p30_message_wallpapers_thread_profile ON chain_message_wallpapers(thread_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_shared_thread ON chain_message_shared_items(thread_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_shared_message ON chain_message_shared_items(message_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_autodownload_profile ON chain_message_autodownload_settings(profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_message_encryption_thread ON chain_message_encryption_status(thread_id);
CREATE INDEX IF NOT EXISTS idx_p30_voice_drafts_thread_profile ON chain_voice_note_drafts(thread_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_voice_playback_message_profile ON chain_voice_note_playback_state(message_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_call_quality_session ON chain_call_quality_events(call_session_id);
CREATE INDEX IF NOT EXISTS idx_p30_call_quality_created ON chain_call_quality_events(created_at);
CREATE INDEX IF NOT EXISTS idx_p30_call_recording_profile ON chain_call_recording_settings(profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_call_device_profile ON chain_call_device_settings(profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_call_waiting_session ON chain_call_waiting_events(call_session_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_roles_group_profile ON chain_group_roles(group_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_announcements_group ON chain_group_announcements(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_adverts_group ON chain_group_adverts(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_analytics_group ON chain_group_analytics(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_verification_group ON chain_group_verification(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_live_group ON chain_group_live_rooms(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_reels_group ON chain_group_reels(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_group_marketplace_group ON chain_group_marketplace_items(group_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_guest_room ON chain_live_guest_requests(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_polls_room ON chain_live_polls(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_battles_room ON chain_live_battles(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_moderation_room ON chain_live_moderation_actions(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_replays_room ON chain_live_replays(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_clips_room ON chain_live_clips(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_shopping_room ON chain_live_shopping_items(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_leaderboard_room ON chain_live_leaderboard(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_live_stream_settings_room ON chain_live_stream_settings(room_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_paid_posts_creator ON chain_creator_paid_posts(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_premium_creator ON chain_creator_premium_content(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_payouts_creator ON chain_creator_payouts(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_gift_conversions_creator ON chain_creator_gift_conversions(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_reports_creator ON chain_creator_revenue_reports(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_sponsorships_creator ON chain_creator_sponsorships(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_badges_creator ON chain_creator_badges(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_supporter_badges_creator ON chain_supporter_badges(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_top_fans_creator ON chain_top_fans(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p30_creator_rankings_creator ON chain_creator_rankings(creator_profile_id);
