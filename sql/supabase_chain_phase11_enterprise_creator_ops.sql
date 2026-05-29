-- CHAIN Phase 11: Enterprise Creator Platform & Operations
-- This migration adds Business Metrics, Brand Campaigns, Global Live Events and Audit Trails.

-- 1. Business Metrics & Daily Reporting
CREATE TABLE IF NOT EXISTS chain_business_metrics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date date UNIQUE NOT NULL DEFAULT CURRENT_DATE,
    dau integer DEFAULT 0,
    new_users integer DEFAULT 0,
    platform_revenue numeric DEFAULT 0,
    creator_earnings numeric DEFAULT 0,
    total_gift_coins integer DEFAULT 0,
    total_stream_minutes interval DEFAULT '00:00:00',
    conversion_rate numeric DEFAULT 0, -- percent
    updated_at timestamptz DEFAULT now()
);

-- 2. Global Live Events (Scheduled & Ticketed)
CREATE TABLE IF NOT EXISTS chain_live_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title text NOT NULL,
    description text,
    event_type text DEFAULT 'livestream', -- 'concert', 'talk', 'exclusive'
    scheduled_start timestamptz NOT NULL,
    estimated_duration interval DEFAULT '01:00:00',
    is_ticketed boolean DEFAULT false,
    ticket_price_coins integer DEFAULT 0,
    max_attendees integer,
    cover_url text,
    status text DEFAULT 'scheduled', -- 'scheduled', 'live', 'completed', 'cancelled'
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_live_events_start ON chain_live_events(scheduled_start);

-- 3. Brand & Sponsor System
CREATE TABLE IF NOT EXISTS chain_brand_campaigns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    brand_name text NOT NULL,
    campaign_title text NOT NULL,
    budget_total numeric DEFAULT 0,
    budget_remaining numeric DEFAULT 0,
    starts_at timestamptz,
    ends_at timestamptz,
    status text DEFAULT 'active',
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_campaigns (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_brand_campaigns(id) ON DELETE CASCADE,
    creator_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    offered_payout_nad numeric DEFAULT 0,
    deliverables text, -- e.g. '1 live stream mention, 2 posts'
    status text DEFAULT 'offered', -- 'offered', 'accepted', 'completed', 'paid'
    created_at timestamptz DEFAULT now(),
    UNIQUE(campaign_id, creator_profile_id)
);

-- 4. Enterprise Audit Logs (Security & Compliance)
CREATE TABLE IF NOT EXISTS chain_enterprise_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id uuid NOT NULL, -- Admin or System User
    actor_type text DEFAULT 'admin',
    action text NOT NULL, -- 'payout_approved', 'creator_suspended', 'campaign_created'
    target_type text,
    target_id uuid,
    metadata jsonb DEFAULT '{}',
    ip_address text,
    created_at timestamptz DEFAULT now()
);

-- 5. Extend Streaming Analytics for Enterprise Insights
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_stream_analytics' AND COLUMN_NAME = 'avg_watch_duration') THEN
        ALTER TABLE chain_stream_analytics ADD COLUMN avg_watch_duration interval;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_stream_analytics' AND COLUMN_NAME = 'follower_conversion_count') THEN
        ALTER TABLE chain_stream_analytics ADD COLUMN follower_conversion_count integer DEFAULT 0;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_stream_analytics' AND COLUMN_NAME = 'geography_json') THEN
        ALTER TABLE chain_stream_analytics ADD COLUMN geography_json jsonb DEFAULT '{}';
    END IF;
END $$;

-- 6. Payout & Finance Batching
CREATE TABLE IF NOT EXISTS chain_payout_batches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_name text NOT NULL,
    total_amount_nad numeric DEFAULT 0,
    payout_count integer DEFAULT 0,
    status text DEFAULT 'pending', -- 'pending', 'processing', 'completed'
    processed_by uuid REFERENCES chain_admin_users(id),
    created_at timestamptz DEFAULT now()
);

DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_wallet_payouts' AND COLUMN_NAME = 'batch_id') THEN
        ALTER TABLE chain_wallet_payouts ADD COLUMN batch_id uuid REFERENCES chain_payout_batches(id) ON DELETE SET NULL;
    END IF;
END $$;
