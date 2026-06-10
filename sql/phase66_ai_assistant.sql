-- Phase 66: Premium AI Assistant Ecosystem
-- All statements idempotent

-- 1. AI chat sessions (conversations)
CREATE TABLE IF NOT EXISTS chain_ai_chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    assistant_type TEXT NOT NULL CHECK(assistant_type IN (
        'general','creator','marketplace','dating_safety','moderation',
        'messages','captions','profile_suggestions','search'
    )),
    title TEXT DEFAULT 'AI Chat',
    messages JSONB DEFAULT '[]'::jsonb,
    context JSONB DEFAULT '{}'::jsonb,
    is_archived BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- 2. AI suggestions log (audit trail)
CREATE TABLE IF NOT EXISTS chain_ai_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    assistant_type TEXT NOT NULL,
    input_text TEXT,
    output_text TEXT NOT NULL,
    context JSONB DEFAULT '{}'::jsonb,
    was_applied BOOLEAN DEFAULT FALSE,
    was_dismissed BOOLEAN DEFAULT FALSE,
    feedback_score INTEGER CHECK(feedback_score >= 1 AND feedback_score <= 5),
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. AI moderation actions log
CREATE TABLE IF NOT EXISTS chain_ai_moderation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    moderator_profile_id UUID NOT NULL,
    target_profile_id UUID,
    target_type TEXT,
    target_id TEXT,
    action_type TEXT NOT NULL CHECK(action_type IN (
        'auto_flag','auto_remove','assisted_review','escalated','dismissed'
    )),
    confidence_score REAL DEFAULT 0.0,
    reason TEXT,
    ai_summary TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. AI user feedback
CREATE TABLE IF NOT EXISTS chain_ai_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    assistant_type TEXT NOT NULL,
    suggestion_id UUID,
    rating INTEGER CHECK(rating >= 1 AND rating <= 5),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_p66_chat_sessions_profile ON chain_ai_chat_sessions(profile_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_p66_chat_sessions_type ON chain_ai_chat_sessions(assistant_type);
CREATE INDEX IF NOT EXISTS idx_p66_suggestions_profile ON chain_ai_suggestions(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_p66_suggestions_type ON chain_ai_suggestions(assistant_type);
CREATE INDEX IF NOT EXISTS idx_p66_moderation_log_mod ON chain_ai_moderation_log(moderator_profile_id);
CREATE INDEX IF NOT EXISTS idx_p66_moderation_log_target ON chain_ai_moderation_log(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_p66_moderation_log_action ON chain_ai_moderation_log(action_type);
CREATE INDEX IF NOT EXISTS idx_p66_feedback_profile ON chain_ai_feedback(profile_id);
CREATE INDEX IF NOT EXISTS idx_p66_feedback_type ON chain_ai_feedback(assistant_type);
