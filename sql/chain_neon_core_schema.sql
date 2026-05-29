CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION chain_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS chain_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id uuid UNIQUE NOT NULL,
    email text,
    username text UNIQUE,
    display_name text,
    full_name text,
    bio text,
    avatar_url text,
    town text,
    city text,
    location text,
    creator_category text,
    is_verified boolean DEFAULT false,
    verified boolean DEFAULT false,
    is_online boolean DEFAULT false,
    is_creator boolean DEFAULT false,
    dating_mode_enabled boolean DEFAULT false,
    profile_completed boolean DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

-- Notifications Engine
CREATE TABLE IF NOT EXISTS chain_notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    event_type text NOT NULL,
    title text,
    body text,
    entity_type text,
    entity_id uuid,
    action_url text,
    is_read boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    read_at timestamptz,
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_notifications_recipient_read ON chain_notifications(recipient_profile_id, is_read, created_at DESC);

-- Reels Engine
CREATE TABLE IF NOT EXISTS chain_reels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    caption text,
    video_url text,
    thumbnail_url text,
    media_url text,
    storage_bucket text,
    storage_path text,
    status text DEFAULT 'published',
    visibility text DEFAULT 'public',
    views_count integer DEFAULT 0,
    likes_count integer DEFAULT 0,
    comments_count integer DEFAULT 0,
    shares_count integer DEFAULT 0,
    is_private boolean NOT NULL DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_reels_status_visibility ON chain_reels(status, visibility, created_at DESC);

-- Ensure columns exist even if table was already there
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS email text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS normalized_email text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS normalized_phone text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS date_of_birth date;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS auth_user_id uuid;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS full_name text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS username text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS residential_address text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS preferred_language text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS interests jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS activities jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS looking_for jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_url text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_url text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS bio text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS creator_category text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_verified boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verified boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_online boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_creator boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS dating_mode_enabled boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_completed boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS wallet_balance numeric DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS onboarding_step text DEFAULT 'account';

-- Notifications
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS event_type text;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS is_read boolean DEFAULT false;

-- Reels
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS video_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS thumbnail_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS media_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS storage_bucket text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS storage_path text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS status text DEFAULT 'published';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS visibility text DEFAULT 'public';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS views_count integer DEFAULT 0;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS shares_count integer DEFAULT 0;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processing_status text DEFAULT 'ready';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS duration_seconds numeric;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS width integer;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS height integer;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS mime_type text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS file_size bigint;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processing_error text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processed_at timestamptz;

-- Messages
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS thread_id uuid REFERENCES chain_message_threads(id) ON DELETE CASCADE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_seen boolean DEFAULT false;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS client_event_id text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivery_status text DEFAULT 'sent';
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_client_event ON chain_messages(thread_id, sender_profile_id, client_event_id) WHERE client_event_id IS NOT NULL;

-- Wallets
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS tx_type text;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS source_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS status text DEFAULT 'pending';
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS balance_after numeric;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS metadata jsonb DEFAULT '{}'::jsonb;
CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_tx_idempotency ON chain_wallet_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Messaging Engine
CREATE TABLE IF NOT EXISTS chain_message_threads (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    created_by_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    thread_type text DEFAULT 'direct',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_thread_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid REFERENCES chain_message_threads(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    last_read_at timestamptz,
    muted boolean DEFAULT false,
    blocked boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (thread_id, profile_id)
);
CREATE INDEX IF NOT EXISTS idx_thread_members_profile ON chain_thread_members(profile_id);
CREATE INDEX IF NOT EXISTS idx_thread_members_thread_profile ON chain_thread_members(thread_id, profile_id);

CREATE TABLE IF NOT EXISTS chain_messages (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id uuid REFERENCES chain_message_threads(id) ON DELETE CASCADE,
    sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    body text,
    media_url text,
    media_type text,
    storage_bucket text,
    storage_path text,
    is_seen boolean DEFAULT false,
    moderation_status text DEFAULT 'clean',
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_messages_thread_created ON chain_messages(thread_id, created_at ASC);

-- Wallet Engine
CREATE TABLE IF NOT EXISTS chain_wallets (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    coin_balance numeric(12,2) DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_wallet_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    tx_type text NOT NULL,
    amount numeric(12,2) NOT NULL DEFAULT 0,
    currency text DEFAULT 'coins',
    status text DEFAULT 'pending',
    source_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    entity_type text,
    entity_id uuid,
    description text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_wallet_tx_profile_created ON chain_wallet_transactions(profile_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chain_gifts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    receiver_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    gift_type text NOT NULL,
    coin_value integer DEFAULT 0,
    entity_type text,
    entity_id uuid,
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_gifts_receiver_created ON chain_gifts(receiver_profile_id, created_at DESC);
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_gifts_idempotency ON chain_gifts(idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_gifts_idempotency ON chain_gifts(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Moderation Engine
CREATE TABLE IF NOT EXISTS chain_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    target_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    entity_type text NOT NULL,
    entity_id uuid,
    reason text NOT NULL,
    details text,
    status text DEFAULT 'open',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    resolved_at timestamptz,
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_reports_status_created ON chain_reports(status, created_at DESC);

CREATE TABLE IF NOT EXISTS chain_blocks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    blocker_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    blocked_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (blocker_profile_id, blocked_profile_id)
);
CREATE INDEX IF NOT EXISTS idx_blocks_blocker_blocked ON chain_blocks(blocker_profile_id, blocked_profile_id);

CREATE TABLE IF NOT EXISTS chain_mutes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    muter_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    muted_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (muter_profile_id, muted_profile_id)
);

-- Presence Engine
CREATE TABLE IF NOT EXISTS chain_presence (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status text DEFAULT 'offline',
    last_seen_at timestamptz DEFAULT now(),
    typing_thread_id uuid,
    typing_until timestamptz,
    updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_presence_status_seen ON chain_presence(status, last_seen_at DESC);

-- Feed Engine
CREATE TABLE IF NOT EXISTS chain_feed_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    event_type text,
    entity_type text,
    entity_id uuid,
    score numeric DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_feed_events_profile_score_created ON chain_feed_events(profile_id, score DESC, created_at DESC);

-- Verification Engine
CREATE TABLE IF NOT EXISTS chain_verification_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    request_type text DEFAULT 'creator',
    status text DEFAULT 'pending',
    document_url text,
    storage_bucket text,
    storage_path text,
    notes text,
    reviewed_by_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    reviewed_at timestamptz,
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_verification_profile_status ON chain_verification_requests(profile_id, status);

-- Background Jobs
CREATE TABLE IF NOT EXISTS chain_background_jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type text NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb,
    queue_name text DEFAULT 'default',
    status text DEFAULT 'queued',
    attempts integer DEFAULT 0,
    max_attempts integer DEFAULT 3,
    run_after timestamptz DEFAULT now(),
    locked_at timestamptz,
    locked_by text,
    last_error text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_background_jobs_status_run_after ON chain_background_jobs(status, run_after);

-- Ensure columns exist even if table was already there
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS date_of_birth date;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS residential_address text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS preferred_language text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS interests jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS activities jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS looking_for jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_url text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_url text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS bio text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS creator_category text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_verified boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verified boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_online boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_creator boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS dating_mode_enabled boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_completed boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS wallet_balance numeric DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS onboarding_step text DEFAULT 'account';

-- Notifications
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS event_type text;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS title text;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS body text;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS entity_type text;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS entity_id uuid;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS action_url text;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS is_read boolean DEFAULT false;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS read_at timestamptz;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Reels
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS caption text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS video_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS thumbnail_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS media_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS storage_bucket text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS storage_path text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS status text DEFAULT 'published';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS visibility text DEFAULT 'public';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS views_count integer DEFAULT 0;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS likes_count integer DEFAULT 0;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS comments_count integer DEFAULT 0;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS shares_count integer DEFAULT 0;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS moderation_status text DEFAULT 'clean';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processing_status text DEFAULT 'ready';
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS duration_seconds numeric;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS width integer;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS height integer;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS mime_type text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS file_size bigint;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processing_error text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processed_at timestamptz;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS transcoded_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS poster_url text;
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Messages
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS thread_id uuid REFERENCES chain_message_threads(id) ON DELETE CASCADE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS body text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_url text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_type text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS storage_bucket text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS storage_path text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_seen boolean DEFAULT false;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS client_event_id text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS moderation_status text DEFAULT 'clean';
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
CREATE UNIQUE INDEX IF NOT EXISTS idx_messages_client_event ON chain_messages(thread_id, sender_profile_id, client_event_id) WHERE client_event_id IS NOT NULL;

-- Wallets
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS tx_type text;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS amount numeric(12,2) DEFAULT 0;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS currency text DEFAULT 'coins';
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS source_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS entity_type text;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS entity_id uuid;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS description text;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS status text DEFAULT 'pending';
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_tx_idempotency ON chain_wallet_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_gifts_idempotency ON chain_gifts(idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS queue_name text DEFAULT 'default';
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS dead_letter_at timestamptz;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS dead_lettered_at timestamptz;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS dead_letter_reason text;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS error_history jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS retry_after timestamptz;
ALTER TABLE chain_background_jobs ADD COLUMN IF NOT EXISTS retry_backoff_seconds integer;
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_idempotency ON chain_background_jobs(idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_wallet_tx_idempotency ON chain_wallet_transactions(idempotency_key) WHERE idempotency_key IS NOT NULL;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS idempotency_key text;
CREATE UNIQUE INDEX IF NOT EXISTS idx_gifts_idempotency ON chain_gifts(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- Message Threads
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS created_by_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS thread_type text DEFAULT 'direct';

-- Thread Members
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS thread_id uuid REFERENCES chain_message_threads(id) ON DELETE CASCADE;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS last_read_at timestamptz;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS muted boolean DEFAULT false;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS blocked boolean DEFAULT false;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Reports
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS reporter_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS target_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS entity_type text;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS entity_id uuid;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS reason text;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS details text;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS status text DEFAULT 'open';
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS resolved_at timestamptz;
ALTER TABLE chain_reports ADD COLUMN IF NOT EXISTS deleted_at timestamptz;

-- Existing tables and triggers
DO $$
DECLARE
    table_name text;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'chain_profiles',
        'chain_reels',
        'chain_message_threads',
        'chain_wallet_transactions',
        'chain_wallets',
        'chain_reports',
        'chain_verification_requests',
        'chain_background_jobs'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch_updated_at ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER trg_%s_touch_updated_at BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION chain_touch_updated_at()',
            table_name,
            table_name
        );
    END LOOP;
END $$;
