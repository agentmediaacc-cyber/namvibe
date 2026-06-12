CREATE INDEX IF NOT EXISTS idx_profiles_username
ON chain_profiles(username);

CREATE INDEX IF NOT EXISTS idx_profiles_email
ON chain_profiles(email);

CREATE INDEX IF NOT EXISTS idx_profiles_auth_user
ON chain_profiles(auth_user_id);

CREATE INDEX IF NOT EXISTS idx_follows_pair
ON chain_follows(
    follower_profile_id,
    following_profile_id
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_run_after
ON chain_background_jobs(
    status,
    run_after
);
