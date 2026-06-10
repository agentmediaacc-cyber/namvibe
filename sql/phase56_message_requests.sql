-- Phase 56: Message Requests for non-friend messaging
CREATE TABLE IF NOT EXISTS chain_message_requests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    from_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    to_profile_id uuid NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    thread_id uuid REFERENCES chain_message_threads(id) ON DELETE SET NULL,
    status text NOT NULL DEFAULT 'pending',
        CHECK (status IN ('pending', 'accepted', 'declined', 'expired')),
    message_body text,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    UNIQUE (from_profile_id, to_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_message_requests_to_status
    ON chain_message_requests(to_profile_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_message_requests_from_status
    ON chain_message_requests(from_profile_id, status, created_at DESC);
