-- Phase 61 — Creator Economy System
-- Idempotent — safe to re-run

-- 1. Add creator level fields to chain_profiles
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS creator_level text DEFAULT 'creator';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS creator_level_updated_at timestamptz;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_views bigint DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_earnings_cents bigint DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_followers int DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_subscribers int DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_tips_cents bigint DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_gifts_cents bigint DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS supporter_count int DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verified_badge text DEFAULT 'none';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS earnings_badge text DEFAULT 'none';

-- 2. Creator level definitions
CREATE TABLE IF NOT EXISTS chain_creator_levels (
    level_key text PRIMARY KEY,
    display_name text NOT NULL,
    min_earnings_cents bigint DEFAULT 0,
    min_followers int DEFAULT 0,
    badge_icon text DEFAULT 'fas fa-star',
    badge_color text DEFAULT '#f7b733',
    description text DEFAULT ''
);

INSERT INTO chain_creator_levels (level_key, display_name, min_earnings_cents, min_followers, badge_icon, badge_color, description)
VALUES
    ('creator', 'Creator', 0, 0, 'fas fa-star', '#f7b733', 'Getting started on the creator journey'),
    ('verified_creator', 'Verified Creator', 50000, 100, 'fas fa-check-circle', '#1e88e5', 'Verified creator with proven content'),
    ('premium_creator', 'Premium Creator', 200000, 500, 'fas fa-crown', '#f7b733', 'Premium creator with established audience'),
    ('business_creator', 'Business Creator', 1000000, 2000, 'fas fa-gem', '#ff0050', 'Top-tier business creator')
ON CONFLICT (level_key) DO NOTHING;

-- 3. Creator real-time stats
CREATE TABLE IF NOT EXISTS chain_creator_stats (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    total_views bigint DEFAULT 0,
    total_earnings_cents bigint DEFAULT 0,
    total_followers int DEFAULT 0,
    total_gifts_cents bigint DEFAULT 0,
    total_tips_cents bigint DEFAULT 0,
    total_subscribers int DEFAULT 0,
    reels_views bigint DEFAULT 0,
    reels_likes bigint DEFAULT 0,
    live_earnings_cents bigint DEFAULT 0,
    live_view_count int DEFAULT 0,
    engagement_rate numeric(5,2) DEFAULT 0,
    updated_at timestamptz DEFAULT now()
);

-- 4. Creator analytics time-series events
CREATE TABLE IF NOT EXISTS chain_creator_analytics_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    event_date date NOT NULL DEFAULT CURRENT_DATE,
    value bigint DEFAULT 0,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, event_type, event_date)
);

CREATE INDEX IF NOT EXISTS idx_creator_analytics_profile_date
    ON chain_creator_analytics_events (profile_id, event_date DESC);
CREATE INDEX IF NOT EXISTS idx_creator_analytics_type
    ON chain_creator_analytics_events (event_type);

-- 5. Creator subscription tiers (extended with monthly/yearly)
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS billing_interval text DEFAULT 'monthly';
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS benefits text[] DEFAULT '{}';
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS subscriber_count int DEFAULT 0;

-- 6. Paid content visibility levels
ALTER TABLE chain_paid_content ADD COLUMN IF NOT EXISTS visibility text DEFAULT 'paid_unlock';

ALTER TABLE chain_paid_content ADD COLUMN IF NOT EXISTS title text DEFAULT '';
ALTER TABLE chain_paid_content ADD COLUMN IF NOT EXISTS description text DEFAULT '';

-- 7. Creator posts visibility enum support
CREATE TABLE IF NOT EXISTS chain_creator_post_visibility (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id uuid NOT NULL,
    creator_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    visibility text NOT NULL DEFAULT 'public',
    min_tier text,
    price_cents bigint DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cpv_creator ON chain_creator_post_visibility (creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_cpv_post ON chain_creator_post_visibility (post_id);

-- 8. Profile upgrade table for tracking creator profile upgrades
CREATE TABLE IF NOT EXISTS chain_creator_profile_upgrades (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    upgrade_type text NOT NULL,
    previous_level text,
    new_level text,
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_cpu_profile ON chain_creator_profile_upgrades (profile_id);
CREATE INDEX IF NOT EXISTS idx_cpu_type ON chain_creator_profile_upgrades (upgrade_type);
