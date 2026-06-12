CREATE INDEX IF NOT EXISTS idx_chain_follows_pair
ON chain_follows (
    follower_profile_id,
    following_profile_id
);

CREATE INDEX IF NOT EXISTS idx_chain_follows_follower
ON chain_follows (follower_profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_follows_following
ON chain_follows (following_profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_unique_key_status
ON chain_background_jobs ((payload->>'_unique_key'), status);
