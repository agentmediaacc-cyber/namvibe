ALTER TABLE IF EXISTS chain_wallet_transactions ADD COLUMN IF NOT EXISTS platform_fee_coins integer default 0;
ALTER TABLE IF EXISTS chain_wallet_transactions ADD COLUMN IF NOT EXISTS net_coins integer default 0;
ALTER TABLE IF EXISTS chain_wallet_transactions ADD COLUMN IF NOT EXISTS balance_before integer default 0;
ALTER TABLE IF EXISTS chain_wallet_transactions ADD COLUMN IF NOT EXISTS balance_after integer default 0;

ALTER TABLE IF EXISTS chain_marketplace_items ADD COLUMN IF NOT EXISTS rejected_by uuid;
ALTER TABLE IF EXISTS chain_marketplace_items ADD COLUMN IF NOT EXISTS rejected_at timestamptz;
ALTER TABLE IF EXISTS chain_marketplace_items ADD COLUMN IF NOT EXISTS rejection_reason text;
ALTER TABLE IF EXISTS chain_marketplace_items ADD COLUMN IF NOT EXISTS is_featured boolean default false;
ALTER TABLE IF EXISTS chain_marketplace_items ADD COLUMN IF NOT EXISTS sales_count integer default 0;
ALTER TABLE IF EXISTS chain_marketplace_items ADD COLUMN IF NOT EXISTS total_earned_coins integer default 0;

ALTER TABLE IF EXISTS chain_wallet_topups ADD COLUMN IF NOT EXISTS rejected_by uuid;
ALTER TABLE IF EXISTS chain_wallet_topups ADD COLUMN IF NOT EXISTS rejected_at timestamptz;
ALTER TABLE IF EXISTS chain_wallet_topups ADD COLUMN IF NOT EXISTS rejection_reason text;

ALTER TABLE IF EXISTS chain_wallet_withdrawals ADD COLUMN IF NOT EXISTS rejected_by uuid;
ALTER TABLE IF EXISTS chain_wallet_withdrawals ADD COLUMN IF NOT EXISTS rejected_at timestamptz;
ALTER TABLE IF EXISTS chain_wallet_withdrawals ADD COLUMN IF NOT EXISTS rejection_reason text;
ALTER TABLE IF EXISTS chain_wallet_withdrawals ADD COLUMN IF NOT EXISTS executed_by uuid;
ALTER TABLE IF EXISTS chain_wallet_withdrawals ADD COLUMN IF NOT EXISTS executed_at timestamptz;
ALTER TABLE IF EXISTS chain_wallet_withdrawals ADD COLUMN IF NOT EXISTS payout_reference text;

CREATE TABLE IF NOT EXISTS chain_platform_ledger (
    id uuid primary key default gen_random_uuid(),
    event_type text,
    source_table text,
    source_id uuid,
    profile_id uuid,
    gross_coins integer default 0,
    platform_fee_coins integer default 0,
    net_coins integer default 0,
    amount_nad numeric default 0,
    description text,
    created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_creator_subscriptions (
    id uuid primary key default gen_random_uuid(),
    subscriber_profile_id uuid,
    creator_profile_id uuid,
    plan_name text,
    price_coins integer default 0,
    status text default 'active',
    started_at timestamptz default now(),
    expires_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_premium_plans (
    id uuid primary key default gen_random_uuid(),
    plan_key text unique,
    plan_name text,
    price_coins integer default 0,
    duration_days integer default 30,
    features jsonb default '{}'::jsonb,
    is_active boolean default true,
    created_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_content_reports (
    id uuid primary key default gen_random_uuid(),
    reporter_profile_id uuid,
    target_type text,
    target_id uuid,
    reason text,
    status text default 'pending',
    reviewed_by uuid,
    reviewed_at timestamptz,
    created_at timestamptz default now()
);

CREATE INDEX IF NOT EXISTS idx_chain_platform_ledger_profile_id ON chain_platform_ledger(profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_creator_subscriptions_creator_profile_id ON chain_creator_subscriptions(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_chain_content_reports_status ON chain_content_reports(status);
CREATE INDEX IF NOT EXISTS idx_chain_marketplace_items_is_featured ON chain_marketplace_items(is_featured);

INSERT INTO chain_premium_plans (plan_key, plan_name, price_coins, duration_days, features, is_active)
SELECT 'starter_creator', 'Starter Creator', 50, 30, '{"boost":"starter","uploads":"standard"}'::jsonb, true
WHERE NOT EXISTS (SELECT 1 FROM chain_premium_plans WHERE plan_key = 'starter_creator');

INSERT INTO chain_premium_plans (plan_key, plan_name, price_coins, duration_days, features, is_active)
SELECT 'premium_creator', 'Premium Creator', 150, 30, '{"boost":"premium","uploads":"priority","insights":true}'::jsonb, true
WHERE NOT EXISTS (SELECT 1 FROM chain_premium_plans WHERE plan_key = 'premium_creator');

INSERT INTO chain_premium_plans (plan_key, plan_name, price_coins, duration_days, features, is_active)
SELECT 'vip_creator', 'VIP Creator', 300, 30, '{"boost":"vip","uploads":"priority","insights":true,"badge":"vip"}'::jsonb, true
WHERE NOT EXISTS (SELECT 1 FROM chain_premium_plans WHERE plan_key = 'vip_creator');
