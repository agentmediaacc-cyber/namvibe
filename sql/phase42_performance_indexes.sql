-- ============================================================
-- PHASE 42: Performance Optimization Indexes
-- Idempotent — safe to re-run
-- ============================================================

-- 1. chain_messages
CREATE INDEX IF NOT EXISTS idx_messages_thread_created ON chain_messages(thread_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_sender ON chain_messages(sender_profile_id);
CREATE INDEX IF NOT EXISTS idx_messages_delivery_status ON chain_messages(delivery_status);
CREATE INDEX IF NOT EXISTS idx_messages_is_seen ON chain_messages(is_seen);

-- 2. chain_thread_members
CREATE INDEX IF NOT EXISTS idx_thread_members_profile ON chain_thread_members(profile_id);
CREATE INDEX IF NOT EXISTS idx_thread_members_thread ON chain_thread_members(thread_id);

-- 3. chain_online_presence
CREATE INDEX IF NOT EXISTS idx_online_presence_profile_status ON chain_online_presence(profile_id, status);

-- 4. chain_message_reactions
CREATE INDEX IF NOT EXISTS idx_reactions_message ON chain_message_reactions(message_id);
CREATE INDEX IF NOT EXISTS idx_reactions_profile ON chain_message_reactions(profile_id);

-- 5. chain_calls
CREATE INDEX IF NOT EXISTS idx_calls_caller_status ON chain_calls(caller_profile_id, status);
CREATE INDEX IF NOT EXISTS idx_calls_receiver_status ON chain_calls(receiver_profile_id, status);
CREATE INDEX IF NOT EXISTS idx_calls_created_at ON chain_calls(created_at DESC);

-- 6. chain_call_participants
CREATE INDEX IF NOT EXISTS idx_call_participants_profile_status ON chain_call_participants(profile_id, status);
CREATE INDEX IF NOT EXISTS idx_call_participants_call ON chain_call_participants(call_id);

-- 7. chain_call_logs
CREATE INDEX IF NOT EXISTS idx_call_logs_profile_created ON chain_call_logs(profile_id, created_at DESC);

-- 8. chain_blocks
CREATE INDEX IF NOT EXISTS idx_blocks_blocker_blocked ON chain_blocks(blocker_profile_id, blocked_profile_id);
