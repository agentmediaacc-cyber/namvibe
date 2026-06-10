-- Phase 64: Premium Live Streaming Ecosystem
-- Multi-host, premium gifts, raid, goals, earnings, moderation
-- All statements idempotent (CREATE IF NOT EXISTS / ALTER IF NOT EXISTS)

-- 1. Multi-host participants with roles
CREATE TABLE IF NOT EXISTS chain_live_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    role TEXT NOT NULL DEFAULT 'viewer' CHECK(role IN ('host','co-host','moderator','viewer')),
    joined_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT TRUE,
    UNIQUE(room_id, profile_id)
);

-- 2. Live streaming earnings (separate from general creator earnings)
CREATE TABLE IF NOT EXISTS chain_live_earnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    room_id UUID,
    source_type TEXT NOT NULL CHECK(source_type IN ('gift','tip','entry_fee','subscription','raid')),
    source_id UUID,
    amount NUMERIC DEFAULT 0,
    currency TEXT DEFAULT 'coins',
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','available','withdrawn')),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. Raid system
CREATE TABLE IF NOT EXISTS chain_live_raids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_room_id UUID NOT NULL,
    target_room_id UUID,
    host_profile_id UUID NOT NULL,
    viewer_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending','active','completed','cancelled')),
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- 4. Stream goals
CREATE TABLE IF NOT EXISTS chain_live_goals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    title TEXT NOT NULL,
    target_amount NUMERIC NOT NULL DEFAULT 0,
    current_amount NUMERIC DEFAULT 0,
    goal_type TEXT DEFAULT 'gifts' CHECK(goal_type IN ('gifts','followers','viewers','tips')),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    reached_at TIMESTAMPTZ
);

-- 5. Chat bans for moderation
CREATE TABLE IF NOT EXISTS chain_live_chat_bans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL,
    profile_id UUID NOT NULL,
    banned_by UUID NOT NULL,
    reason TEXT,
    duration_minutes INTEGER DEFAULT 0,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 6. Enhance existing gift catalog with premium fields
ALTER TABLE chain_gift_catalog ADD COLUMN IF NOT EXISTS tier TEXT DEFAULT 'standard';
ALTER TABLE chain_gift_catalog ADD COLUMN IF NOT EXISTS animation_url TEXT;
ALTER TABLE chain_gift_catalog ADD COLUMN IF NOT EXISTS sort_order INTEGER DEFAULT 0;

-- 7. Enhance live rooms with premium streaming settings
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS premium_only BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS stream_description TEXT;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS tags TEXT[];
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS is_mature BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS max_viewers INTEGER DEFAULT 0;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS co_host_limit INTEGER DEFAULT 3;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS chat_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_live_rooms ADD COLUMN IF NOT EXISTS gift_total_earned NUMERIC DEFAULT 0;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_p64_participants_room ON chain_live_participants(room_id, role);
CREATE INDEX IF NOT EXISTS idx_p64_participants_profile ON chain_live_participants(profile_id);
CREATE INDEX IF NOT EXISTS idx_p64_earnings_profile ON chain_live_earnings(profile_id, status);
CREATE INDEX IF NOT EXISTS idx_p64_earnings_room ON chain_live_earnings(room_id);
CREATE INDEX IF NOT EXISTS idx_p64_raids_source ON chain_live_raids(source_room_id);
CREATE INDEX IF NOT EXISTS idx_p64_raids_target ON chain_live_raids(target_room_id);
CREATE INDEX IF NOT EXISTS idx_p64_goals_room ON chain_live_goals(room_id, is_active);
CREATE INDEX IF NOT EXISTS idx_p64_chat_bans_room ON chain_live_chat_bans(room_id, profile_id);
CREATE INDEX IF NOT EXISTS idx_p64_gift_catalog_sort ON chain_gift_catalog(is_active, sort_order);
