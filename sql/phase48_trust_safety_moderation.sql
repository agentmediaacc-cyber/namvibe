-- Phase 48: Trust, Safety, Moderation, Anti-Spam, Fraud Protection
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS chain_trust_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID UNIQUE,
    trust_score INTEGER DEFAULT 70,
    risk_score INTEGER DEFAULT 0,
    spam_score INTEGER DEFAULT 0,
    fraud_score INTEGER DEFAULT 0,
    report_count INTEGER DEFAULT 0,
    warning_count INTEGER DEFAULT 0,
    restriction_count INTEGER DEFAULT 0,
    last_reviewed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_user_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reporter_profile_id UUID,
    reported_profile_id UUID,
    content_type TEXT,
    content_id UUID,
    reason TEXT,
    details TEXT,
    status TEXT DEFAULT 'open',
    severity TEXT DEFAULT 'medium',
    moderator_profile_id UUID,
    resolution_note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_moderation_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID,
    content_type TEXT,
    content_id UUID,
    queue_type TEXT,
    risk_level TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'pending',
    reason TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    assigned_to_profile_id UUID,
    created_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_moderation_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    moderator_profile_id UUID,
    target_profile_id UUID,
    content_type TEXT,
    content_id UUID,
    action_type TEXT,
    reason TEXT,
    duration_minutes INTEGER,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_spam_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID,
    event_type TEXT,
    score INTEGER DEFAULT 0,
    content_type TEXT,
    content_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_fraud_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID,
    wallet_transaction_id UUID,
    payout_request_id UUID,
    event_type TEXT,
    score INTEGER DEFAULT 0,
    severity TEXT DEFAULT 'medium',
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_creator_verification_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    creator_profile_id UUID,
    verification_type TEXT DEFAULT 'creator',
    status TEXT DEFAULT 'pending',
    submitted_data JSONB DEFAULT '{}'::jsonb,
    admin_note TEXT,
    reviewed_by_profile_id UUID,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    reviewed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chain_rate_limit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID,
    ip_hash TEXT,
    action_type TEXT,
    count INTEGER DEFAULT 1,
    window_seconds INTEGER DEFAULT 60,
    blocked BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_trust_scores_profile ON chain_trust_scores(profile_id);
CREATE INDEX IF NOT EXISTS idx_trust_scores_created ON chain_trust_scores(created_at);
CREATE INDEX IF NOT EXISTS idx_user_reports_reporter ON chain_user_reports(reporter_profile_id);
CREATE INDEX IF NOT EXISTS idx_user_reports_reported ON chain_user_reports(reported_profile_id);
CREATE INDEX IF NOT EXISTS idx_user_reports_status ON chain_user_reports(status);
CREATE INDEX IF NOT EXISTS idx_user_reports_severity ON chain_user_reports(severity);
CREATE INDEX IF NOT EXISTS idx_user_reports_created ON chain_user_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_user_reports_content ON chain_user_reports(content_type, content_id);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_profile ON chain_moderation_queue(profile_id);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_status ON chain_moderation_queue(status);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_risk ON chain_moderation_queue(risk_level);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_created ON chain_moderation_queue(created_at);
CREATE INDEX IF NOT EXISTS idx_moderation_queue_content ON chain_moderation_queue(content_type, content_id);
CREATE INDEX IF NOT EXISTS idx_moderation_actions_target ON chain_moderation_actions(target_profile_id);
CREATE INDEX IF NOT EXISTS idx_moderation_actions_created ON chain_moderation_actions(created_at);
CREATE INDEX IF NOT EXISTS idx_spam_events_profile ON chain_spam_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_spam_events_created ON chain_spam_events(created_at);
CREATE INDEX IF NOT EXISTS idx_spam_events_content ON chain_spam_events(content_type, content_id);
CREATE INDEX IF NOT EXISTS idx_fraud_events_profile ON chain_fraud_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_fraud_events_wallet_tx ON chain_fraud_events(wallet_transaction_id);
CREATE INDEX IF NOT EXISTS idx_fraud_events_payout ON chain_fraud_events(payout_request_id);
CREATE INDEX IF NOT EXISTS idx_fraud_events_severity ON chain_fraud_events(severity);
CREATE INDEX IF NOT EXISTS idx_fraud_events_created ON chain_fraud_events(created_at);
CREATE INDEX IF NOT EXISTS idx_creator_verification_profile ON chain_creator_verification_requests(creator_profile_id);
CREATE INDEX IF NOT EXISTS idx_creator_verification_status ON chain_creator_verification_requests(status);
CREATE INDEX IF NOT EXISTS idx_creator_verification_created ON chain_creator_verification_requests(submitted_at);
CREATE INDEX IF NOT EXISTS idx_rate_limit_profile ON chain_rate_limit_events(profile_id);
CREATE INDEX IF NOT EXISTS idx_rate_limit_action ON chain_rate_limit_events(action_type);
CREATE INDEX IF NOT EXISTS idx_rate_limit_created ON chain_rate_limit_events(created_at);
