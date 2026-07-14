-- ═══════════════════════════════════════════════════════════════
-- Phase: NVC Economy — Coin Packs, Verification Payments, Themes
-- ═══════════════════════════════════════════════════════════════

-- 1. Coin Packs catalog
CREATE TABLE IF NOT EXISTS chain_coin_packs (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    coins           INT NOT NULL,
    price_nad       INT NOT NULL,
    bonus_coins     INT DEFAULT 0,
    is_active       BOOLEAN DEFAULT TRUE,
    sort_order      INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO chain_coin_packs (id, name, coins, price_nad, bonus_coins, sort_order) VALUES
    ('starter',  'Starter',  10,   50,   0,  1),
    ('bronze',   'Bronze',   25,   125,  0,  2),
    ('silver',   'Silver',   50,   250,  0,  3),
    ('gold',     'Gold',     100,  500,  0,  4),
    ('platinum', 'Platinum', 250,  1250, 0,  5),
    ('diamond',  'Diamond',  500,  2500, 25, 6),
    ('elite',    'Elite',    1000, 5000, 50, 7)
ON CONFLICT (id) DO NOTHING;

-- 2. Profile Themes catalog
CREATE TABLE IF NOT EXISTS chain_profile_themes (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    coins           INT NOT NULL,
    nad_price       INT NOT NULL,
    preview_colors  TEXT,       -- CSS gradient for preview swatch
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT now()
);

INSERT INTO chain_profile_themes (id, name, coins, nad_price, preview_colors) VALUES
    ('basic',       'Basic Theme',     2,  10,  'linear-gradient(135deg,#6b7280,#4b5563)'),
    ('neon',        'Neon Theme',      5,  25,  'linear-gradient(135deg,#06b6d4,#8b5cf6)'),
    ('royal_gold',  'Royal Gold',      10, 50,  'linear-gradient(135deg,#f59e0b,#d97706)'),
    ('galaxy',      'Galaxy Theme',    15, 75,  'linear-gradient(135deg,#a855f7,#7c3aed)'),
    ('diamond',     'Diamond Theme',   25, 125, 'linear-gradient(135deg,#1e293b,#475569)')
ON CONFLICT (id) DO NOTHING;

-- 3. Purchased themes per profile
CREATE TABLE IF NOT EXISTS chain_profile_theme_purchases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    theme_id        TEXT NOT NULL REFERENCES chain_profile_themes(id),
    active_theme    BOOLEAN DEFAULT FALSE,
    purchased_at    TIMESTAMPTZ DEFAULT now(),
    UNIQUE(profile_id, theme_id)
);

-- 4. Verification payments ledger
CREATE TABLE IF NOT EXISTS chain_verification_payments (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id          UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    verification_type   TEXT NOT NULL,  -- 'blue','business','government','ngo'
    coins_paid          INT NOT NULL DEFAULT 0,
    nad_paid            INT NOT NULL DEFAULT 0,
    transaction_id      UUID,           -- FK to chain_wallet_transactions
    status              TEXT DEFAULT 'completed',  -- completed/refunded/failed
    created_at          TIMESTAMPTZ DEFAULT now()
);

-- 5. Add payment tracking to chain_user_verifications
ALTER TABLE chain_user_verifications ADD COLUMN IF NOT EXISTS verification_type TEXT DEFAULT 'blue';
ALTER TABLE chain_user_verifications ADD COLUMN IF NOT EXISTS payment_id UUID REFERENCES chain_verification_payments(id);
ALTER TABLE chain_user_verifications ADD COLUMN IF NOT EXISTS profile_completed BOOLEAN DEFAULT FALSE;

-- 6. Add active_theme column to chain_profiles
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS active_theme TEXT DEFAULT 'default';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS theme_purchased BOOLEAN DEFAULT FALSE;

-- 7. Subscription tiers for creator subscriptions
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS tier_coins INT DEFAULT 0;
ALTER TABLE chain_creator_subscriptions ADD COLUMN IF NOT EXISTS tier_nad INT DEFAULT 0;

-- 8. Advertising transactions table
CREATE TABLE IF NOT EXISTS chain_advertising (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    ad_type         TEXT NOT NULL,  -- boost_post, boost_reel, homepage_promo, trending_placement
    target_id       UUID,           -- post/reel id
    coins_spent     INT NOT NULL,
    nad_spent       INT NOT NULL,
    days            INT DEFAULT 1,
    starts_at       TIMESTAMPTZ DEFAULT now(),
    ends_at         TIMESTAMPTZ,
    status          TEXT DEFAULT 'active',  -- active/expired/cancelled
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 9. Extra storage subscriptions
CREATE TABLE IF NOT EXISTS chain_storage_subscriptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id      UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    storage_tier    TEXT NOT NULL,  -- 50gb, 200gb, 1tb
    storage_gb      INT NOT NULL,
    coins_monthly   INT NOT NULL,
    nad_monthly     INT NOT NULL,
    status          TEXT DEFAULT 'active',  -- active/cancelled/expired
    started_at      TIMESTAMPTZ DEFAULT now(),
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- 10. Indexes
CREATE INDEX IF NOT EXISTS idx_verification_payments_profile ON chain_verification_payments(profile_id);
CREATE INDEX IF NOT EXISTS idx_theme_purchases_profile ON chain_profile_theme_purchases(profile_id);
CREATE INDEX IF NOT EXISTS idx_advertising_profile ON chain_advertising(profile_id);
CREATE INDEX IF NOT EXISTS idx_storage_subs_profile ON chain_storage_subscriptions(profile_id);
