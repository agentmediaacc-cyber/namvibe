-- CHAIN Phase 10: Launch Readiness & Scale
-- This migration adds Viral Growth, Advanced Wallets, Analytics, and Creator Economy structures.

-- 1. Viral Growth System
CREATE TABLE IF NOT EXISTS chain_referrals (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    referrer_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    referred_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    referral_code text NOT NULL,
    reward_status text DEFAULT 'pending', -- 'pending', 'claimed'
    reward_coins integer DEFAULT 0,
    created_at timestamptz DEFAULT now(),
    UNIQUE(referred_profile_id)
);

CREATE TABLE IF NOT EXISTS chain_share_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    entity_type text NOT NULL, -- 'profile', 'reel', 'live_room', 'marketplace_item'
    entity_id uuid NOT NULL,
    platform text, -- 'whatsapp', 'facebook', 'copy_link'
    created_at timestamptz DEFAULT now()
);

-- 2. Advanced Wallet & Escrow
CREATE TABLE IF NOT EXISTS chain_wallet_payouts (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    amount_nad numeric NOT NULL,
    coins_deducted integer NOT NULL,
    payout_method text NOT NULL, -- 'fnb', 'mtc_maris', 'bank_transfer'
    status text DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    reference_id text,
    processed_at timestamptz,
    created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_escrow_transactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    seller_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    item_type text NOT NULL, -- 'marketplace', 'subscription', 'ticket'
    item_id uuid NOT NULL,
    amount_coins integer NOT NULL,
    status text DEFAULT 'held', -- 'held', 'released', 'refunded'
    release_at timestamptz,
    created_at timestamptz DEFAULT now()
);

-- 3. Creator Economy: Tickets & Subscriptions
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'is_ticketed') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN is_ticketed boolean DEFAULT false;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'chain_live_rooms' AND COLUMN_NAME = 'ticket_price_coins') THEN
        ALTER TABLE chain_live_rooms ADD COLUMN ticket_price_coins integer DEFAULT 0;
    END IF;
END $$;

-- 4. Analytics Events
CREATE TABLE IF NOT EXISTS chain_analytics_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    event_name text NOT NULL, -- 'page_view', 'reel_watch', 'stream_join', 'app_install'
    entity_type text,
    entity_id uuid,
    metadata jsonb DEFAULT '{}',
    device_type text,
    ip_address text,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_analytics_name ON chain_analytics_events(event_name);
CREATE INDEX IF NOT EXISTS idx_chain_analytics_profile ON chain_analytics_events(profile_id);

-- 5. Content Moderation Queue
CREATE TABLE IF NOT EXISTS chain_moderation_queue (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type text NOT NULL, -- 'reel', 'post', 'comment', 'profile'
    entity_id uuid NOT NULL,
    reporter_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    reason text,
    ai_score numeric, -- Score from moderation engine
    status text DEFAULT 'pending', -- 'pending', 'resolved', 'dismissed'
    action_taken text,
    created_at timestamptz DEFAULT now()
);

-- 6. PWA & Device Tracking
CREATE TABLE IF NOT EXISTS chain_user_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    device_token text, -- For Push Notifications
    device_type text, -- 'android', 'ios', 'pwa'
    app_version text,
    last_active_at timestamptz DEFAULT now(),
    UNIQUE(profile_id, device_token)
);
