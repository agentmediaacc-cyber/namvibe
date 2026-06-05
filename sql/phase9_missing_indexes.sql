-- PHASE 9 MISSING INDEXES
-- Optimized for messaging, status, and privacy lookups

-- Messages Performance
CREATE INDEX IF NOT EXISTS idx_chain_messages_thread_created 
ON chain_messages (thread_id, created_at ASC) 
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chain_messages_sender 
ON chain_messages (sender_profile_id, created_at DESC) 
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chain_messages_client_event 
ON chain_messages (client_event_id);

-- Thread Members & Inbox
CREATE INDEX IF NOT EXISTS idx_chain_thread_members_profile 
ON chain_thread_members (profile_id, is_pinned DESC, last_read_at DESC);

-- Reactions & Deletions
CREATE INDEX IF NOT EXISTS idx_chain_message_reactions_msg 
ON chain_message_reactions (message_id);

CREATE INDEX IF NOT EXISTS idx_chain_message_deletions_msg_profile 
ON chain_message_deletions (message_id, profile_id);

-- Status Privacy & Mutual Connections
-- For checking mutual follows efficiently
CREATE INDEX IF NOT EXISTS idx_chain_follows_mutual 
ON chain_follows (follower_profile_id, following_profile_id);

-- Status Viewers
CREATE INDEX IF NOT EXISTS idx_chain_status_viewers_status 
ON chain_status_viewers (status_id, viewed_at DESC);

-- Close Friends table (missing in schema earlier)
CREATE TABLE IF NOT EXISTS chain_close_friends (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    friend_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at timestamptz DEFAULT now(),
    UNIQUE (profile_id, friend_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_chain_close_friends_profile 
ON chain_close_friends (profile_id);

-- Call Sessions
CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_conversation 
ON chain_call_sessions (conversation_id, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_call_sessions_participants 
ON chain_call_sessions (caller_profile_id, receiver_profile_id);
