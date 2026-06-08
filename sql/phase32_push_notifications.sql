CREATE TABLE IF NOT EXISTS chain_push_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL,
    endpoint text NOT NULL,
    p256dh text NOT NULL,
    auth text NOT NULL,
    user_agent text DEFAULT '',
    device_type text DEFAULT 'web',
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    last_seen_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_push_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid,
    event_type text NOT NULL,
    title text DEFAULT '',
    body text DEFAULT '',
    payload jsonb DEFAULT '{}',
    sent boolean DEFAULT false,
    provider_missing boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    sent_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_notification_preferences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL,
    messages boolean DEFAULT true,
    calls boolean DEFAULT true,
    live boolean DEFAULT true,
    groups boolean DEFAULT true,
    wallet boolean DEFAULT true,
    safety boolean DEFAULT true,
    creator_updates boolean DEFAULT true,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE(profile_id)
);

CREATE TABLE IF NOT EXISTS chain_device_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL,
    device_type text DEFAULT 'web',
    user_agent text DEFAULT '',
    ip_address text DEFAULT '',
    is_active boolean DEFAULT true,
    last_seen_at timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_profile ON chain_push_subscriptions(profile_id);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_active ON chain_push_subscriptions(is_active);
CREATE INDEX IF NOT EXISTS idx_push_events_profile ON chain_push_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_push_events_sent ON chain_push_events(sent);
CREATE INDEX IF NOT EXISTS idx_notif_preferences_profile ON chain_notification_preferences(profile_id);
CREATE INDEX IF NOT EXISTS idx_device_sessions_profile ON chain_device_sessions(profile_id);

-- Performance indexes for slow queries
CREATE INDEX IF NOT EXISTS idx_profiles_auth_user_id ON chain_profiles(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_username ON chain_profiles(username);
CREATE INDEX IF NOT EXISTS idx_threads_updated_at ON chain_message_threads(updated_at);
CREATE INDEX IF NOT EXISTS idx_thread_members_profile ON chain_thread_members(profile_id);
CREATE INDEX IF NOT EXISTS idx_messages_thread_created ON chain_messages(thread_id, created_at);
CREATE INDEX IF NOT EXISTS idx_call_sessions_caller ON chain_call_sessions(caller_profile_id, started_at);
CREATE INDEX IF NOT EXISTS idx_call_sessions_receiver ON chain_call_sessions(receiver_profile_id, started_at);
CREATE INDEX IF NOT EXISTS idx_live_rooms_status ON chain_live_rooms(status, created_at);
CREATE INDEX IF NOT EXISTS idx_groups_visibility ON chain_groups(visibility, created_at);
CREATE INDEX IF NOT EXISTS idx_push_subscriptions_profile_id ON chain_push_subscriptions(profile_id);
