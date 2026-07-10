-- ══════════════════════════════════════════════════════════════
-- PHASE 88 — NAMVIBE ADVERTISING PLATFORM
-- Complete schema: campaigns, creatives, targeting, analytics,
-- payments, moderation, fraud detection, coupons, promotions
-- ══════════════════════════════════════════════════════════════

-- 0. Expand chain_ad_campaigns with missing columns
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ad_type TEXT DEFAULT 'feed';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS content_url TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS target_url TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS daily_budget INT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS budget_cents BIGINT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS daily_budget_cents BIGINT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS priority INT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS bid_type TEXT DEFAULT 'auto';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS bid_amount DECIMAL(10,2) DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS bid_amount_cents BIGINT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS spent_amount DECIMAL(12,2) DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS spent_amount_cents BIGINT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS funded_amount_cents BIGINT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS daily_spend_cents BIGINT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS funded_at TIMESTAMPTZ;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS target_audience JSONB DEFAULT '{}';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS review_note TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS reviewed_by UUID REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ai_score DECIMAL(5,2);
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ai_flagged BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ai_flags JSONB DEFAULT '[]';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS impressions_count INT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS clicks_count INT DEFAULT 0;

UPDATE chain_ad_campaigns
SET owner_id = COALESCE(owner_id, profile_id),
    title = COALESCE(title, name),
    content_url = COALESCE(content_url, media_url),
    starts_at = COALESCE(starts_at, start_date),
    ends_at = COALESCE(ends_at, end_date),
    impressions_count = COALESCE(impressions_count, impressions, 0),
    clicks_count = COALESCE(clicks_count, clicks, 0)
WHERE owner_id IS NULL
   OR title IS NULL
   OR content_url IS NULL
   OR starts_at IS NULL
   OR ends_at IS NULL
   OR impressions_count IS NULL
   OR clicks_count IS NULL;

ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_status_check;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_status_check
    CHECK (status IN ('draft','pending','pending_payment','funded','pending_review','active','paused','rejected','completed','expired','cancelled','budget_exhausted'));
ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_budget_cents_nonnegative;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_budget_cents_nonnegative CHECK (budget_cents >= 0);
ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_daily_budget_cents_nonnegative;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_daily_budget_cents_nonnegative CHECK (daily_budget_cents >= 0);
ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_spent_amount_cents_nonnegative;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_spent_amount_cents_nonnegative CHECK (spent_amount_cents >= 0);
ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_funded_amount_cents_nonnegative;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_funded_amount_cents_nonnegative CHECK (funded_amount_cents >= 0);
ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_daily_spend_cents_nonnegative;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_daily_spend_cents_nonnegative CHECK (daily_spend_cents >= 0);

CREATE INDEX IF NOT EXISTS idx_ad_campaigns_category ON chain_ad_campaigns(category);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_priority ON chain_ad_campaigns(priority);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_deleted ON chain_ad_campaigns(is_deleted);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_owner ON chain_ad_campaigns(owner_id);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_status_dates ON chain_ad_campaigns(status, starts_at, ends_at);

-- 0b. Impression and click event tables used by serving/tracking
CREATE TABLE IF NOT EXISTS chain_ad_impressions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    client_event_id text,
    viewed_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_impressions_campaign ON chain_ad_impressions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_impressions_profile ON chain_ad_impressions(profile_id);
CREATE INDEX IF NOT EXISTS idx_ad_impressions_viewed_at ON chain_ad_impressions(viewed_at);

CREATE TABLE IF NOT EXISTS chain_ad_clicks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    client_event_id text,
    clicked_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_clicks_campaign ON chain_ad_clicks(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_clicks_profile ON chain_ad_clicks(profile_id);
CREATE INDEX IF NOT EXISTS idx_ad_clicks_clicked_at ON chain_ad_clicks(clicked_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_impressions_client_event ON chain_ad_impressions(campaign_id, profile_id, client_event_id) WHERE client_event_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_clicks_client_event ON chain_ad_clicks(campaign_id, profile_id, client_event_id) WHERE client_event_id IS NOT NULL;

-- 1. chain_advertisers — advertiser profiles
CREATE TABLE IF NOT EXISTS chain_advertisers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid UNIQUE NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    business_name text,
    business_category text,
    business_website text,
    business_description text,
    tax_id text,
    billing_email text,
    billing_address text,
    is_verified boolean DEFAULT false,
    verification_docs text,
    total_spent DECIMAL(14,2) DEFAULT 0,
    lifetime_spent DECIMAL(14,2) DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_advertisers_profile ON chain_advertisers(profile_id);
CREATE INDEX IF NOT EXISTS idx_advertisers_verified ON chain_advertisers(is_verified);

-- 2. chain_ad_creatives — individual ad creatives (a campaign can have many)
CREATE TABLE IF NOT EXISTS chain_ad_creatives (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    creative_type text NOT NULL DEFAULT 'image' CHECK (creative_type IN ('image','video','reel','story','carousel','text')),
    media_url text,
    media_id uuid,
    headline text,
    description text,
    cta_text text DEFAULT 'Learn More',
    destination_url text,
    thumbnail_url text,
    sort_order int DEFAULT 0,
    duration_seconds int DEFAULT 0,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_creatives_campaign ON chain_ad_creatives(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_creatives_profile ON chain_ad_creatives(profile_id);
CREATE INDEX IF NOT EXISTS idx_ad_creatives_type ON chain_ad_creatives(creative_type);

-- 3. chain_ad_placements — where campaigns run
CREATE TABLE IF NOT EXISTS chain_ad_placements (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    placement_type text NOT NULL CHECK (placement_type IN (
        'feed','reels','stories','discover','marketplace','search','dating','live','notifications'
    )),
    is_active boolean DEFAULT true,
    bid_multiplier DECIMAL(5,2) DEFAULT 1.00,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_placements_campaign ON chain_ad_placements(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_placements_type ON chain_ad_placements(placement_type);

-- 4. chain_ad_targeting — audience targeting rules
CREATE TABLE IF NOT EXISTS chain_ad_targeting (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL UNIQUE REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    countries text[] DEFAULT '{}',
    regions text[] DEFAULT '{}',
    cities text[] DEFAULT '{}',
    languages text[] DEFAULT '{}',
    age_min int DEFAULT 13,
    age_max int DEFAULT 100,
    genders text[] DEFAULT '{}',
    interests text[] DEFAULT '{}',
    device_types text[] DEFAULT '{}',
    targeting_verified boolean DEFAULT false,
    targeting_creators boolean DEFAULT false,
    targeting_businesses boolean DEFAULT false,
    exclude_followers boolean DEFAULT false,
    custom_audience_ids uuid[] DEFAULT '{}',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_targeting_campaign ON chain_ad_targeting(campaign_id);

-- 5. chain_ad_analytics — daily rollup stats
CREATE TABLE IF NOT EXISTS chain_ad_analytics (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    date date NOT NULL,
    impressions int DEFAULT 0,
    unique_reach int DEFAULT 0,
    clicks int DEFAULT 0,
    ctr DECIMAL(8,4) DEFAULT 0,
    cost_per_click DECIMAL(10,4) DEFAULT 0,
    cost_per_mille DECIMAL(10,4) DEFAULT 0,
    spend DECIMAL(12,2) DEFAULT 0,
    video_views int DEFAULT 0,
    watch_time_seconds int DEFAULT 0,
    conversions int DEFAULT 0,
    purchases int DEFAULT 0,
    messages_started int DEFAULT 0,
    calls_started int DEFAULT 0,
    website_visits int DEFAULT 0,
    profile_visits int DEFAULT 0,
    follows_gained int DEFAULT 0,
    shares int DEFAULT 0,
    saves int DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    UNIQUE(campaign_id, date)
);

CREATE INDEX IF NOT EXISTS idx_ad_analytics_campaign ON chain_ad_analytics(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_analytics_date ON chain_ad_analytics(date);
CREATE INDEX IF NOT EXISTS idx_ad_analytics_profile ON chain_ad_analytics(profile_id);

-- 6. chain_ad_payments — billing and payment records
CREATE TABLE IF NOT EXISTS chain_ad_payments (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_ad_campaigns(id) ON DELETE SET NULL,
    profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    amount DECIMAL(12,2) NOT NULL,
    amount_cents BIGINT DEFAULT 0,
    currency text DEFAULT 'NAD',
    payment_method text CHECK (payment_method IN ('wallet','card','mobile_money','bank_transfer','promo','coupon')),
    payment_provider text,
    provider_reference text,
    wallet_transaction_id uuid REFERENCES chain_wallet_transactions(id) ON DELETE SET NULL,
    idempotency_key text,
    status text DEFAULT 'pending' CHECK (status IN ('pending','completed','failed','refunded','cancelled')),
    description text,
    invoice_url text,
    paid_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_payments_campaign ON chain_ad_payments(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_payments_profile ON chain_ad_payments(profile_id);
CREATE INDEX IF NOT EXISTS idx_ad_payments_status ON chain_ad_payments(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ad_payments_idempotency ON chain_ad_payments(idempotency_key) WHERE idempotency_key IS NOT NULL;

-- 7. chain_ad_moderation — AI review + fraud detection queue
CREATE TABLE IF NOT EXISTS chain_ad_moderation (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    creative_id uuid REFERENCES chain_ad_creatives(id) ON DELETE SET NULL,
    review_status text DEFAULT 'pending' CHECK (review_status IN ('pending','ai_reviewed','approved','rejected','flagged')),
    ai_score DECIMAL(5,2),
    ai_flagged boolean DEFAULT false,
    ai_flags jsonb DEFAULT '[]',
    ai_recommendation text,
    fraud_score DECIMAL(5,2),
    fraud_flags jsonb DEFAULT '[]',
    fraud_details text,
    reviewed_by uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    reviewed_at timestamptz,
    notes text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_moderation_campaign ON chain_ad_moderation(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_moderation_status ON chain_ad_moderation(review_status);
CREATE INDEX IF NOT EXISTS idx_ad_moderation_reviewer ON chain_ad_moderation(reviewed_by);

-- 8. chain_ad_coupons — discount/promo codes
CREATE TABLE IF NOT EXISTS chain_ad_coupons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text UNIQUE NOT NULL,
    description text,
    discount_type text NOT NULL CHECK (discount_type IN ('percentage','fixed')),
    discount_value DECIMAL(10,2) NOT NULL,
    min_spend DECIMAL(10,2) DEFAULT 0,
    max_discount DECIMAL(10,2),
    usage_limit int DEFAULT 1,
    used_count int DEFAULT 0,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    is_active boolean DEFAULT true,
    starts_at timestamptz DEFAULT now(),
    expires_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_coupons_code ON chain_ad_coupons(code);
CREATE INDEX IF NOT EXISTS idx_ad_coupons_active ON chain_ad_coupons(is_active);

-- 9. chain_ad_promotions — links to promoted content
CREATE TABLE IF NOT EXISTS chain_ad_promotions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid NOT NULL REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    content_type text NOT NULL CHECK (content_type IN ('post','reel','story','marketplace','live','business','creator','event','dating_profile')),
    content_id uuid NOT NULL,
    profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_promotions_campaign ON chain_ad_promotions(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_promotions_content ON chain_ad_promotions(content_type, content_id);

-- 10. chain_ad_fraud_events — fraud detection log
CREATE TABLE IF NOT EXISTS chain_ad_fraud_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    fraud_type text NOT NULL CHECK (fraud_type IN (
        'fake_click','bot_traffic','click_farm','duplicate_click','fake_impression',
        'fake_account','invalid_traffic','proxy_click','automated_click'
    )),
    score DECIMAL(5,2),
    ip_address text,
    user_agent text,
    details jsonb DEFAULT '{}',
    detected_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ad_fraud_campaign ON chain_ad_fraud_events(campaign_id);
CREATE INDEX IF NOT EXISTS idx_ad_fraud_type ON chain_ad_fraud_events(fraud_type);
CREATE INDEX IF NOT EXISTS idx_ad_fraud_profile ON chain_ad_fraud_events(profile_id);

-- 11. Auto-update updated_at triggers
CREATE OR REPLACE FUNCTION chain_ad_touch_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_ad_campaigns_updated ON chain_ad_campaigns;
CREATE TRIGGER trg_ad_campaigns_updated
    BEFORE UPDATE ON chain_ad_campaigns
    FOR EACH ROW EXECUTE FUNCTION chain_ad_touch_updated_at();

DROP TRIGGER IF EXISTS trg_advertisers_updated ON chain_advertisers;
CREATE TRIGGER trg_advertisers_updated
    BEFORE UPDATE ON chain_advertisers
    FOR EACH ROW EXECUTE FUNCTION chain_ad_touch_updated_at();

DROP TRIGGER IF EXISTS trg_ad_targeting_updated ON chain_ad_targeting;
CREATE TRIGGER trg_ad_targeting_updated
    BEFORE UPDATE ON chain_ad_targeting
    FOR EACH ROW EXECUTE FUNCTION chain_ad_touch_updated_at();
