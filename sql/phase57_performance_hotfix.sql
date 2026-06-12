CREATE INDEX IF NOT EXISTS idx_chain_profiles_username
ON chain_profiles(username);

CREATE INDEX IF NOT EXISTS idx_chain_profiles_email
ON chain_profiles(email);

CREATE INDEX IF NOT EXISTS idx_chain_profiles_normalized_email
ON chain_profiles(normalized_email);

CREATE INDEX IF NOT EXISTS idx_chain_profiles_auth_user_id
ON chain_profiles(auth_user_id);

CREATE INDEX IF NOT EXISTS idx_chain_follows_pair
ON chain_follows(follower_profile_id, following_profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_follows_follower
ON chain_follows(follower_profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_follows_following
ON chain_follows(following_profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_status_run_after
ON chain_background_jobs(status, run_after);

CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_unique_key
ON chain_background_jobs((payload->>'_unique_key'));

CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_type_status
ON chain_background_jobs(job_type, status);

CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_idempotency_key
ON chain_background_jobs(idempotency_key);

DELETE FROM chain_background_jobs
WHERE ctid IN (
    SELECT ctid
    FROM (
        SELECT ctid, ROW_NUMBER() OVER (
            PARTITION BY payload->>'_unique_key'
            ORDER BY created_at DESC
        ) as rn
        FROM chain_background_jobs
        WHERE payload->>'_unique_key' IS NOT NULL
          AND status IN ('queued', 'running')
          AND payload ? '_unique_key'
    ) t
    WHERE t.rn > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_chain_jobs_active_unique_key
ON chain_background_jobs((payload->>'_unique_key'))
WHERE status IN ('queued', 'running')
  AND payload ? '_unique_key';
