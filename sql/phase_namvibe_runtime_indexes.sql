CREATE INDEX IF NOT EXISTS idx_namvibe_posts_profile_created
    ON chain_posts(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_namvibe_reels_profile_created
    ON chain_reels(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_namvibe_stories_profile_created
    ON chain_stories(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_namvibe_live_rooms_profile_created
    ON chain_live_rooms(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_namvibe_profiles_auth_user_id
    ON chain_profiles(auth_user_id);

CREATE INDEX IF NOT EXISTS idx_namvibe_profiles_email
    ON chain_profiles(email);

CREATE INDEX IF NOT EXISTS idx_namvibe_wallets_profile_id
    ON chain_wallets(profile_id);
