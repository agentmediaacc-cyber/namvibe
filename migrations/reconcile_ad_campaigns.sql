-- Reconcile chain_ad_campaigns schema between Phase 157 (ads_service) and Phase 158d (business_page_service)
-- Run against Neon. Idempotent — safe to run multiple times.

-- Phase 157 columns (canonical):
--   id, owner_id, media_id, title, content_url, target_url, ad_type, budget, status, starts_at, ends_at, impressions_count, clicks_count, created_at

-- Phase 158d columns to preserve/add:
--   objective, media_type, target_audience, is_sponsored, updated_at, reach, engagement

-- 1. Add Phase 158d columns if missing
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS objective TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS media_type TEXT DEFAULT 'image';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS target_audience JSONB DEFAULT '{}';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS is_sponsored BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS reach INT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS engagement INT DEFAULT 0;

-- 2. Add Phase 157 columns if missing (when Phase 158d ran first)
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS owner_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS media_id UUID;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS title TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS content_url TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS target_url TEXT;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ad_type TEXT DEFAULT 'feed';
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS starts_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS ends_at TIMESTAMPTZ;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS impressions_count INT DEFAULT 0;
ALTER TABLE chain_ad_campaigns ADD COLUMN IF NOT EXISTS clicks_count INT DEFAULT 0;

-- 3. Migrate data: copy profile_id -> owner_id if owner_id is null and profile_id exists
UPDATE chain_ad_campaigns SET owner_id = profile_id WHERE owner_id IS NULL AND profile_id IS NOT NULL;
UPDATE chain_ad_campaigns SET title = name WHERE title IS NULL AND name IS NOT NULL;
UPDATE chain_ad_campaigns SET content_url = media_url WHERE content_url IS NULL AND media_url IS NOT NULL;
UPDATE chain_ad_campaigns SET starts_at = start_date WHERE starts_at IS NULL AND start_date IS NOT NULL;
UPDATE chain_ad_campaigns SET ends_at = end_date WHERE ends_at IS NULL AND end_date IS NOT NULL;
UPDATE chain_ad_campaigns SET impressions_count = impressions WHERE impressions_count IS NULL AND impressions IS NOT NULL;
UPDATE chain_ad_campaigns SET clicks_count = clicks WHERE clicks_count IS NULL AND clicks IS NOT NULL;

-- 4. Add check constraint for status (relaxed to include both schemas' values)
ALTER TABLE chain_ad_campaigns DROP CONSTRAINT IF EXISTS chain_ad_campaigns_status_check;
ALTER TABLE chain_ad_campaigns ADD CONSTRAINT chain_ad_campaigns_status_check
    CHECK (status IN ('draft','active','paused','ended','pending','completed','rejected'));

-- 5. Indexes
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_owner ON chain_ad_campaigns(owner_id);
CREATE INDEX IF NOT EXISTS idx_ad_campaigns_status ON chain_ad_campaigns(status);

-- 6. Ensure chain_ad_impressions and chain_ad_clicks exist
CREATE TABLE IF NOT EXISTS chain_ad_impressions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    viewed_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ad_impressions_campaign ON chain_ad_impressions(campaign_id);

CREATE TABLE IF NOT EXISTS chain_ad_clicks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id uuid REFERENCES chain_ad_campaigns(id) ON DELETE CASCADE,
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    clicked_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ad_clicks_campaign ON chain_ad_clicks(campaign_id);

-- 7. Drop Phase 158d columns that conflict (safe after migration above)
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS profile_id;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS name;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS media_url;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS start_date;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS end_date;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS daily_budget;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS total_budget;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS impressions;
ALTER TABLE chain_ad_campaigns DROP COLUMN IF EXISTS clicks;
