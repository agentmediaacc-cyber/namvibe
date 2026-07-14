-- ============================================================
-- Call & Messaging Rules Migration
-- ============================================================
-- who_can_message: 'everyone' (public) | 'friends' (private)
-- Controls whether non-friends can send messages.
-- Calling always requires friendship.

-- Ensure who_can_message column exists (default: 'everyone' = public messaging ON)
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_message TEXT DEFAULT 'everyone';

-- Ensure who_can_call column exists (default: 'friends')
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_call TEXT DEFAULT 'friends';

-- Index for quick lookup of public messaging profiles
CREATE INDEX IF NOT EXISTS idx_profiles_who_can_message ON chain_profiles(who_can_message) WHERE deleted_at IS NULL;
