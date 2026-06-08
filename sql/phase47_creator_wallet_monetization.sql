-- ============================================================
-- PHASE 47: Creator Wallet, Monetization, Tips, Payouts & Earnings
-- Idempotent -- safe to re-run
-- ============================================================

-- 1. Extend chain_wallets with new columns
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS balance_cents BIGINT DEFAULT 0;
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS pending_balance_cents BIGINT DEFAULT 0;
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS lifetime_earned_cents BIGINT DEFAULT 0;
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS lifetime_spent_cents BIGINT DEFAULT 0;
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS id UUID;

CREATE INDEX IF NOT EXISTS idx_wallets_status ON chain_wallets(status);

-- 2. Extend chain_wallet_transactions with new columns
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS wallet_id UUID;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS counterparty_profile_id UUID DEFAULT NULL;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS transaction_type TEXT;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS direction TEXT;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS amount_cents BIGINT;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS reference_type TEXT DEFAULT NULL;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS reference_id UUID DEFAULT NULL;
ALTER TABLE chain_wallet_transactions ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_wallet_tx_counterparty ON chain_wallet_transactions(counterparty_profile_id);

-- 3. Extend chain_gifts for catalog columns
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS name TEXT;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS emoji TEXT;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS price_cents BIGINT;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS amount_cents BIGINT;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD';
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS transaction_id UUID DEFAULT NULL;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_gifts ADD COLUMN IF NOT EXISTS message TEXT DEFAULT NULL;

-- 4. chain_creator_earnings (new)
CREATE TABLE IF NOT EXISTS chain_creator_earnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID,
    source_profile_id UUID DEFAULT NULL,
    earning_type TEXT,
    gross_amount_cents BIGINT,
    platform_fee_cents BIGINT DEFAULT 0,
    net_amount_cents BIGINT,
    currency TEXT DEFAULT 'NAD',
    status TEXT DEFAULT 'available',
    reference_type TEXT DEFAULT NULL,
    reference_id UUID DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_earnings_creator ON chain_creator_earnings(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_earnings_source ON chain_creator_earnings(source_profile_id);
CREATE INDEX IF NOT EXISTS idx_earnings_type ON chain_creator_earnings(earning_type);
CREATE INDEX IF NOT EXISTS idx_earnings_status ON chain_creator_earnings(status);
CREATE INDEX IF NOT EXISTS idx_earnings_created ON chain_creator_earnings(created_at);

-- 5. chain_creator_subscriptions (new)
CREATE TABLE IF NOT EXISTS chain_creator_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_profile_id UUID,
    creator_profile_id UUID,
    tier_name TEXT DEFAULT 'basic',
    price_cents BIGINT,
    currency TEXT DEFAULT 'NAD',
    status TEXT DEFAULT 'active',
    started_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ DEFAULT NULL,
    cancelled_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_subs_subscriber ON chain_creator_subscriptions(subscriber_profile_id);
CREATE INDEX IF NOT EXISTS idx_subs_creator ON chain_creator_subscriptions(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_subs_status ON chain_creator_subscriptions(status);

-- 6. chain_paid_content (new)
CREATE TABLE IF NOT EXISTS chain_paid_content (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID,
    content_type TEXT,
    content_id UUID,
    price_cents BIGINT,
    currency TEXT DEFAULT 'NAD',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_paid_content_creator ON chain_paid_content(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_paid_content_type ON chain_paid_content(content_type);
CREATE INDEX IF NOT EXISTS idx_paid_content_active ON chain_paid_content(active);

-- 7. chain_content_purchases (new)
CREATE TABLE IF NOT EXISTS chain_content_purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_profile_id UUID,
    creator_profile_id UUID,
    paid_content_id UUID,
    amount_cents BIGINT,
    currency TEXT DEFAULT 'NAD',
    transaction_id UUID DEFAULT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_purchases_buyer ON chain_content_purchases(buyer_profile_id);
CREATE INDEX IF NOT EXISTS idx_purchases_creator ON chain_content_purchases(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_purchases_content ON chain_content_purchases(paid_content_id);

-- 8. chain_payout_requests (replaces old chain_wallet_payouts)
CREATE TABLE IF NOT EXISTS chain_payout_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID,
    amount_cents BIGINT,
    currency TEXT DEFAULT 'NAD',
    payout_method TEXT DEFAULT 'bank',
    payout_details JSONB DEFAULT '{}',
    status TEXT DEFAULT 'pending',
    admin_note TEXT DEFAULT NULL,
    requested_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ DEFAULT NULL,
    paid_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_payouts_creator ON chain_payout_requests(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_payouts_status ON chain_payout_requests(status);
CREATE INDEX IF NOT EXISTS idx_payouts_requested ON chain_payout_requests(requested_at);

-- 9. chain_wallet_risk_events (new)
CREATE TABLE IF NOT EXISTS chain_wallet_risk_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID,
    event_type TEXT,
    severity TEXT DEFAULT 'medium',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_risk_events_profile ON chain_wallet_risk_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_risk_events_type ON chain_wallet_risk_events(event_type);

-- Seed default gift catalog entries (idempotent)
INSERT INTO chain_gifts (name, emoji, price_cents, amount_cents, currency, active, gift_type)
SELECT 'Rose', '🌹', 500, 500, 'NAD', TRUE, 'Rose'
WHERE NOT EXISTS (SELECT 1 FROM chain_gifts WHERE name = 'Rose' AND active = TRUE);

INSERT INTO chain_gifts (name, emoji, price_cents, amount_cents, currency, active, gift_type)
SELECT 'Fire', '🔥', 1000, 1000, 'NAD', TRUE, 'Fire'
WHERE NOT EXISTS (SELECT 1 FROM chain_gifts WHERE name = 'Fire' AND active = TRUE);

INSERT INTO chain_gifts (name, emoji, price_cents, amount_cents, currency, active, gift_type)
SELECT 'Crown', '👑', 2500, 2500, 'NAD', TRUE, 'Crown'
WHERE NOT EXISTS (SELECT 1 FROM chain_gifts WHERE name = 'Crown' AND active = TRUE);

INSERT INTO chain_gifts (name, emoji, price_cents, amount_cents, currency, active, gift_type)
SELECT 'Diamond', '💎', 5000, 5000, 'NAD', TRUE, 'Diamond'
WHERE NOT EXISTS (SELECT 1 FROM chain_gifts WHERE name = 'Diamond' AND active = TRUE);

INSERT INTO chain_gifts (name, emoji, price_cents, amount_cents, currency, active, gift_type)
SELECT 'Lion', '🦁', 10000, 10000, 'NAD', TRUE, 'Lion'
WHERE NOT EXISTS (SELECT 1 FROM chain_gifts WHERE name = 'Lion' AND active = TRUE);
