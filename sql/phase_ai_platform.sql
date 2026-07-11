-- Phase 1A: NamVibe AI Platform foundation
-- Intentionally avoids foreign keys so deployment stays compatible across
-- environments where profile table variants may differ.

CREATE TABLE IF NOT EXISTS chain_ai_user_profiles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL UNIQUE,
    inferred_interests jsonb NOT NULL DEFAULT '[]'::jsonb,
    explicit_interests jsonb NOT NULL DEFAULT '[]'::jsonb,
    preferred_languages jsonb NOT NULL DEFAULT '[]'::jsonb,
    preferred_content_types jsonb NOT NULL DEFAULT '[]'::jsonb,
    region text,
    town text,
    recommendation_settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    safety_settings jsonb NOT NULL DEFAULT '{}'::jsonb,
    onboarding_completed boolean NOT NULL DEFAULT false,
    interaction_count bigint NOT NULL DEFAULT 0,
    last_interaction_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_ai_user_profiles_profile_id
    ON chain_ai_user_profiles (profile_id);

CREATE INDEX IF NOT EXISTS idx_chain_ai_user_profiles_last_interaction_at
    ON chain_ai_user_profiles (last_interaction_at DESC);

CREATE TABLE IF NOT EXISTS chain_ai_interactions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL,
    target_type text NOT NULL,
    target_id text NOT NULL,
    action_type text NOT NULL,
    action_weight numeric(8,3) NOT NULL DEFAULT 1,
    source_surface text,
    session_id text,
    dwell_time_ms integer,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT chk_chain_ai_interactions_target_type
        CHECK (target_type IN ('post', 'reel', 'story', 'profile', 'live', 'marketplace', 'event', 'business', 'dating_profile', 'hashtag')),
    CONSTRAINT chk_chain_ai_interactions_action_type
        CHECK (action_type IN ('impression', 'view', 'open', 'like', 'unlike', 'comment', 'share', 'save', 'unsave', 'follow', 'unfollow', 'friend_request', 'friend_accept', 'message', 'call', 'hide', 'report', 'block', 'purchase', 'join', 'complete'))
);

CREATE INDEX IF NOT EXISTS idx_chain_ai_interactions_profile_created_at
    ON chain_ai_interactions (profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_ai_interactions_target
    ON chain_ai_interactions (target_type, target_id);

CREATE INDEX IF NOT EXISTS idx_chain_ai_interactions_action_created_at
    ON chain_ai_interactions (action_type, created_at DESC);

CREATE TABLE IF NOT EXISTS chain_ai_recommendation_events (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid NOT NULL,
    recommendation_type text NOT NULL,
    target_type text NOT NULL,
    target_id text NOT NULL,
    score numeric(12,6) NOT NULL DEFAULT 0,
    reason_codes jsonb NOT NULL DEFAULT '[]'::jsonb,
    algorithm_version text NOT NULL,
    request_id text,
    shown_at timestamptz NOT NULL DEFAULT now(),
    opened_at timestamptz,
    engaged_at timestamptz,
    dismissed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_chain_ai_recommendation_events_profile_shown_at
    ON chain_ai_recommendation_events (profile_id, shown_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_ai_recommendation_events_type_shown_at
    ON chain_ai_recommendation_events (recommendation_type, shown_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_ai_recommendation_events_request_id
    ON chain_ai_recommendation_events (request_id);

CREATE TABLE IF NOT EXISTS chain_ai_provider_usage (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid,
    feature_name text NOT NULL,
    provider_name text NOT NULL,
    model_name text,
    request_id text,
    input_units integer NOT NULL DEFAULT 0,
    output_units integer NOT NULL DEFAULT 0,
    latency_ms integer,
    status text NOT NULL,
    error_code text,
    estimated_cost numeric(14,6) NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_ai_provider_usage_feature_created_at
    ON chain_ai_provider_usage (feature_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_ai_provider_usage_provider_created_at
    ON chain_ai_provider_usage (provider_name, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_chain_ai_provider_usage_profile_created_at
    ON chain_ai_provider_usage (profile_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chain_ai_feature_flags (
    feature_key text PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT false,
    rollout_percentage integer NOT NULL DEFAULT 0,
    configuration jsonb NOT NULL DEFAULT '{}'::jsonb,
    updated_by uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO chain_ai_feature_flags (feature_key, enabled, rollout_percentage)
VALUES
    ('ai_interaction_tracking', true, 100),
    ('ai_recommendations', false, 0),
    ('ai_external_provider', false, 0),
    ('ai_caption_generator', false, 0),
    ('ai_comment_suggestions', false, 0),
    ('ai_translation', false, 0),
    ('ai_moderation', false, 0),
    ('ai_dating_matching', false, 0),
    ('ai_founder_assistant', false, 0)
ON CONFLICT (feature_key) DO NOTHING;
