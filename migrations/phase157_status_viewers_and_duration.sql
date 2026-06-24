-- Phase 157 — Status Viewer Tracking, Duration, and Locked Media Support
-- Run against Neon

-- 1. Add missing columns to chain_status_posts
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS duration_seconds integer DEFAULT 0;
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS background_color text;
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS text_content text;
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS views_count integer DEFAULT 0;
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS storage_bucket text;
ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS storage_path text;

-- 2. chain_status_views table (unique per status_id + viewer_profile_id)
CREATE TABLE IF NOT EXISTS chain_status_views (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    status_id uuid REFERENCES chain_status_posts(id) ON DELETE CASCADE,
    viewer_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    viewed_at timestamptz DEFAULT now(),
    reaction text,
    reply_message text,
    UNIQUE(status_id, viewer_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_status_views_status_id ON chain_status_views(status_id);
CREATE INDEX IF NOT EXISTS idx_status_views_viewer ON chain_status_views(viewer_profile_id);

-- 3. chain_ad_campaigns table (ad campaigns for non-intrusive feed ads)
CREATE TABLE IF NOT EXISTS chain_ad_campaigns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    media_id uuid,
    title text NOT NULL,
    content_url text,
    target_url text,
    ad_type text DEFAULT 'feed',
    budget integer DEFAULT 0,
    status text DEFAULT 'draft' CHECK (status IN ('draft','active','paused','ended')),
    starts_at timestamptz DEFAULT now(),
    ends_at timestamptz,
    impressions_count integer DEFAULT 0,
    clicks_count integer DEFAULT 0,
    created_at timestamptz DEFAULT now()
);

ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS owner_id uuid;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS media_id uuid;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS budget integer DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS starts_at timestamptz DEFAULT now();
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ends_at timestamptz;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS impressions_count integer DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS clicks_count integer DEFAULT 0;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS profile_id;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS start_date;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS end_date;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS daily_budget;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS total_budget;

CREATE INDEX IF NOT EXISTS idx_ad_campaigns_profile ON chain_ad_campaigns(owner_id);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_status ON chain_ad_campaigns(status);

-- 4. chain_ad_impressions table
CREATE TABLE IF NOT EXISTS chain_ad_impressions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    viewed_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_impressions_campaign ON chain_ad_impressions(campaign_id);

-- 5. chain_ad_clicks table
CREATE TABLE IF NOT EXISTS chain_ad_clicks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    clicked_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_clicks_campaign ON chain_ad_clicks(campaign_id);

-- 6. Ensure chain_status_posts has visibility check constraint
ALTER TABLE chain_status_posts DROP CONSTRAINT IF EXISTS chain_status_posts_visibility_check;
ALTER TABLE chain_status_posts ADD CONSTRAINT chain_status_posts_visibility_check
    CHECK (visibility IN ('public','followers','private','subscribers','locked'));
