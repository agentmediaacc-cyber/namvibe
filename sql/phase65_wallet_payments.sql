-- Phase 65: Premium Wallet, Payments, Payouts & Ledger
-- All statements idempotent

-- 1. Immutable ledger entries (audit trail)
CREATE TABLE IF NOT EXISTS chain_wallet_ledger_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    wallet_id UUID,
    transaction_id UUID,
    entry_type TEXT NOT NULL CHECK(entry_type IN (
        'deposit','withdrawal','payout','tip_sent','tip_received',
        'gift_sent','gift_received','subscription_payment','subscription_received',
        'marketplace_purchase','marketplace_sale','refund','adjustment','platform_fee'
    )),
    amount_cents BIGINT NOT NULL DEFAULT 0,
    balance_before_cents BIGINT NOT NULL DEFAULT 0,
    balance_after_cents BIGINT NOT NULL DEFAULT 0,
    pending_before_cents BIGINT NOT NULL DEFAULT 0,
    pending_after_cents BIGINT NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'completed' CHECK(status IN ('pending','completed','failed','reversed','cancelled')),
    reference_type TEXT,
    reference_id UUID,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. Payout methods (masked)
CREATE TABLE IF NOT EXISTS chain_payout_methods (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    provider TEXT NOT NULL CHECK(provider IN ('bank','mobile_wallet','paypal','manual')),
    account_name TEXT NOT NULL DEFAULT '',
    masked_account TEXT NOT NULL DEFAULT '',
    country TEXT DEFAULT 'NA',
    currency TEXT DEFAULT 'NAD',
    is_default BOOLEAN DEFAULT FALSE,
    verification_status TEXT DEFAULT 'unverified' CHECK(verification_status IN ('unverified','pending','verified','failed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Payment intents
CREATE TABLE IF NOT EXISTS chain_payment_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    intent_type TEXT NOT NULL CHECK(intent_type IN (
        'tip','gift','subscription','marketplace_purchase','payout','refund'
    )),
    amount_cents BIGINT NOT NULL DEFAULT 0,
    platform_fee_cents BIGINT NOT NULL DEFAULT 0,
    net_amount_cents BIGINT NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','processing','completed','failed','cancelled','reversed')),
    source_profile_id UUID,
    target_profile_id UUID,
    reference_id UUID,
    idempotency_key TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 4. Idempotency keys
CREATE TABLE IF NOT EXISTS chain_wallet_idempotency_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key TEXT NOT NULL UNIQUE,
    profile_id UUID NOT NULL,
    action_type TEXT NOT NULL,
    request_hash TEXT,
    response_status INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_p65_ledger_profile ON chain_wallet_ledger_entries(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p65_ledger_transaction ON chain_wallet_ledger_entries(transaction_id);
CREATE INDEX IF NOT EXISTS idx_p65_ledger_type ON chain_wallet_ledger_entries(entry_type, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p65_payout_methods_profile ON chain_payout_methods(profile_id, is_default);
CREATE INDEX IF NOT EXISTS idx_p65_payment_intents_profile ON chain_payment_intents(profile_id, status);
CREATE INDEX IF NOT EXISTS idx_p65_payment_intents_key ON chain_payment_intents(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_p65_idempotency_keys_lookup ON chain_wallet_idempotency_keys(idempotency_key, action_type);
CREATE INDEX IF NOT EXISTS idx_p65_idempotency_keys_profile ON chain_wallet_idempotency_keys(profile_id);

-- Additional safe columns on chain_wallets
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS withdrawable_balance_cents BIGINT DEFAULT 0;
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'NAD';
ALTER TABLE chain_wallets ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ;
