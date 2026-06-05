-- CHAIN PHASE 11 SCHEMA UPDATES

-- 1. Profile Enhancements for Scale & Business
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS account_type text DEFAULT 'personal'; -- personal, creator, business
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_name text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_website text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_opening_hours jsonb DEFAULT '{}'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_location_data jsonb DEFAULT '{}'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_services jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_products jsonb DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_contact_email text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_contact_phone text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS trust_score numeric(4,2) DEFAULT 5.0; -- 0.0 to 10.0
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS last_trust_update timestamptz;

-- 2. Live Stream Economy & Moderation
CREATE TABLE IF NOT EXISTS chain_live_moderators (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid NOT NULL, -- References chain_live_rooms(id)
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    permissions jsonb DEFAULT '["mute", "remove"]'::jsonb,
    created_at timestamptz DEFAULT now(),
    UNIQUE(room_id, profile_id)
);

CREATE TABLE IF NOT EXISTS chain_live_pinned_comments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id uuid NOT NULL,
    comment_id uuid NOT NULL, -- References chain_live_comments(id)
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE, -- Who pinned it
    created_at timestamptz DEFAULT now(),
    UNIQUE(room_id) -- Only one pinned comment per room
);

-- 3. Search Intelligence
CREATE TABLE IF NOT EXISTS chain_search_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    query text NOT NULL,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_search_history_profile ON chain_search_history(profile_id, created_at DESC);

-- 4. Platform Analytics (Daily Aggregates)
CREATE TABLE IF NOT EXISTS chain_analytics_daily (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date date UNIQUE NOT NULL DEFAULT CURRENT_DATE,
    dau integer DEFAULT 0,
    mau integer DEFAULT 0,
    new_users integer DEFAULT 0,
    creator_growth integer DEFAULT 0,
    total_revenue_nad numeric(12,2) DEFAULT 0,
    live_room_count integer DEFAULT 0,
    total_view_minutes integer DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

-- 5. Creator Analytics (Periodic Snapshot)
CREATE TABLE IF NOT EXISTS chain_creator_analytics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    metric_date date NOT NULL,
    profile_views integer DEFAULT 0,
    post_reach integer DEFAULT 0,
    reel_reach integer DEFAULT 0,
    live_reach integer DEFAULT 0,
    total_earnings_coins integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, metric_date)
);

-- 6. Feed Quality & Caching Support
CREATE TABLE IF NOT EXISTS chain_content_quality_scores (
    entity_type text NOT NULL, -- post, reel, live_room
    entity_id uuid NOT NULL,
    quality_score numeric(5,2) DEFAULT 1.0,
    engagement_score numeric(12,4) DEFAULT 0,
    diversity_category text,
    updated_at timestamptz DEFAULT now(),
    PRIMARY KEY (entity_type, entity_id)
);

-- 7. API Readiness (Version Tracking)
CREATE TABLE IF NOT EXISTS chain_api_versions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    platform text NOT NULL, -- android, ios, web
    current_version text NOT NULL,
    min_required_version text NOT NULL,
    update_url text,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_profiles_account_type ON chain_profiles(account_type);
CREATE INDEX IF NOT EXISTS idx_profiles_trust_score ON chain_profiles(trust_score DESC);
