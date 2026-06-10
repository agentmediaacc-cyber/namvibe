-- Phase 63 — Premium Dating System
-- Idempotent — safe to re-run

-- 1. Dating Profiles (extra columns on chain_profiles)
CREATE TABLE IF NOT EXISTS chain_dating_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid UNIQUE NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    dating_mode_on boolean DEFAULT true,
    relationship_goal text DEFAULT 'friendship',
    age_range_min int DEFAULT 18,
    age_range_max int DEFAULT 99,
    location_preference text DEFAULT '',
    bio text DEFAULT '',
    interests text[] DEFAULT '{}',
    photos text[] DEFAULT '{}',
    verification_status text DEFAULT 'unverified',
    trust_score int DEFAULT 50,
    safety_badge boolean DEFAULT false,
    hide_from_contacts boolean DEFAULT false,
    visible_to_verified_only boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dating_profiles_profile ON chain_dating_profiles (profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_profiles_mode ON chain_dating_profiles (profile_id, dating_mode_on);
CREATE INDEX IF NOT EXISTS idx_dating_profiles_goal ON chain_dating_profiles (relationship_goal);
CREATE INDEX IF NOT EXISTS idx_dating_profiles_trust ON chain_dating_profiles (trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_dating_profiles_verified ON chain_dating_profiles (verification_status);

-- 2. Likes / Passes / Super Likes
CREATE TABLE IF NOT EXISTS chain_dating_likes (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    target_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    action_type text NOT NULL DEFAULT 'like',
    is_mutual boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dating_likes_actor ON chain_dating_likes (actor_profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_likes_target ON chain_dating_likes (target_profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_likes_actor_target ON chain_dating_likes (actor_profile_id, target_profile_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dating_likes_unique ON chain_dating_likes (actor_profile_id, target_profile_id, action_type);
CREATE INDEX IF NOT EXISTS idx_dating_likes_type ON chain_dating_likes (action_type);
CREATE INDEX IF NOT EXISTS idx_dating_likes_mutual ON chain_dating_likes (is_mutual) WHERE is_mutual = true;

-- 3. Matches
CREATE TABLE IF NOT EXISTS chain_dating_matches (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id_a uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    profile_id_b uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    compatibility_score int DEFAULT 50,
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dating_matches_pair ON chain_dating_matches (
    LEAST(profile_id_a, profile_id_b),
    GREATEST(profile_id_a, profile_id_b)
);
CREATE INDEX IF NOT EXISTS idx_dating_matches_a ON chain_dating_matches (profile_id_a);
CREATE INDEX IF NOT EXISTS idx_dating_matches_b ON chain_dating_matches (profile_id_b);
CREATE INDEX IF NOT EXISTS idx_dating_matches_active ON chain_dating_matches (is_active);

-- 4. Reports
CREATE TABLE IF NOT EXISTS chain_dating_reports (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reported_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    reason text NOT NULL DEFAULT '',
    details text DEFAULT '',
    is_resolved boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dating_reports_reporter ON chain_dating_reports (reporter_profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_reports_reported ON chain_dating_reports (reported_profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_reports_resolved ON chain_dating_reports (is_resolved);

-- 5. Blocks
CREATE TABLE IF NOT EXISTS chain_dating_blocks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    blocker_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    blocked_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_dating_blocks_pair ON chain_dating_blocks (blocker_profile_id, blocked_profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_blocks_blocker ON chain_dating_blocks (blocker_profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_blocks_blocked ON chain_dating_blocks (blocked_profile_id);

-- 6. Preferences
CREATE TABLE IF NOT EXISTS chain_dating_preferences (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid UNIQUE NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    interested_in text DEFAULT 'everyone',
    min_age int DEFAULT 18,
    max_age int DEFAULT 99,
    max_distance_km int DEFAULT 100,
    show_me boolean DEFAULT true,
    only_verified boolean DEFAULT false,
    hide_from_contacts boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dating_preferences_profile ON chain_dating_preferences (profile_id);
CREATE INDEX IF NOT EXISTS idx_dating_preferences_show ON chain_dating_preferences (show_me) WHERE show_me = true;
