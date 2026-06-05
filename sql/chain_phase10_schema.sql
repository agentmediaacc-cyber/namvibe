-- CHAIN PHASE 10 SCHEMA UPDATES

-- Messages Extension for Premium Features
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS read_at timestamptz; -- For Blue Ticks
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS sticker_id text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS gif_url text;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS location_lat double precision;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS location_lng double precision;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS contact_data jsonb;

-- Thread Management (Inbox vs Requests)
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS folder_type text DEFAULT 'primary'; -- primary, request, spam, archived
ALTER TABLE chain_message_threads ADD COLUMN IF NOT EXISTS is_e2ee boolean DEFAULT false;

-- Presence Enhancement
CREATE TABLE IF NOT EXISTS chain_presence (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    status text DEFAULT 'offline', -- online, away, dnd, offline
    last_seen_at timestamptz DEFAULT now(),
    custom_status text,
    updated_at timestamptz DEFAULT now()
);

-- Safety & Spam Control
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_fake boolean DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS trust_score float DEFAULT 1.0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS last_ip text;

CREATE TABLE IF NOT EXISTS chain_spam_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    target_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    thread_id uuid REFERENCES chain_message_threads(id) ON DELETE SET NULL,
    reason text,
    details text,
    created_at timestamptz DEFAULT now()
);

-- Stickers Library
CREATE TABLE IF NOT EXISTS chain_stickers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    pack_name text,
    sticker_url text NOT NULL,
    created_at timestamptz DEFAULT now()
);
