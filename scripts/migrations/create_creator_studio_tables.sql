-- Creator Studio Phase 7 Migration
-- Safe migration — uses IF NOT EXISTS, no DROP/TRUNCATE/DELETE

-- Content drafts
CREATE TABLE IF NOT EXISTS chain_creator_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    content_type VARCHAR(32) NOT NULL DEFAULT 'post',
    title TEXT DEFAULT '',
    body TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_creator_drafts_profile ON chain_creator_drafts(profile_id, updated_at DESC);

-- Scheduled posts
CREATE TABLE IF NOT EXISTS chain_creator_scheduled_posts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    content_type VARCHAR(32) NOT NULL DEFAULT 'post',
    title TEXT DEFAULT '',
    body TEXT DEFAULT '',
    media_url TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    scheduled_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'scheduled',
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_creator_scheduled_profile ON chain_creator_scheduled_posts(profile_id, scheduled_at);
CREATE INDEX IF NOT EXISTS idx_creator_scheduled_status ON chain_creator_scheduled_posts(status, scheduled_at)
    WHERE status = 'scheduled';

-- Keyword filters for comment moderation
CREATE TABLE IF NOT EXISTS chain_creator_keyword_filters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    keyword TEXT NOT NULL,
    action VARCHAR(16) NOT NULL DEFAULT 'hide',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_creator_keyword_filters_profile ON chain_creator_keyword_filters(profile_id, is_active);

-- Hidden words (auto-hidden from comments)
CREATE TABLE IF NOT EXISTS chain_creator_hidden_words (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, word)
);

-- Auto-review queue for flagged comments
CREATE TABLE IF NOT EXISTS chain_creator_comment_review_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    comment_id UUID,
    commenter_profile_id UUID,
    comment_body TEXT,
    reason VARCHAR(64) DEFAULT 'keyword_match',
    status VARCHAR(16) NOT NULL DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_creator_review_queue_profile ON chain_creator_comment_review_queue(profile_id, status);

-- Link hub (business tools)
CREATE TABLE IF NOT EXISTS chain_creator_link_hub (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title VARCHAR(128) NOT NULL,
    url TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, url)
);

CREATE INDEX IF NOT EXISTS idx_creator_link_hub_profile ON chain_creator_link_hub(profile_id, sort_order);

-- Business hours
CREATE TABLE IF NOT EXISTS chain_creator_business_hours (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
    open_time TIME,
    close_time TIME,
    is_closed BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE(profile_id, day_of_week)
);

-- Creator milestones
CREATE TABLE IF NOT EXISTS chain_creator_milestones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    milestone_type VARCHAR(64) NOT NULL,
    milestone_value REAL NOT NULL DEFAULT 0,
    label TEXT DEFAULT '',
    reached_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notified BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_creator_milestones_profile ON chain_creator_milestones(profile_id, reached_at DESC);

-- Weekly summaries
CREATE TABLE IF NOT EXISTS chain_creator_weekly_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    summary JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, week_start)
);

-- Content archive (soft-delete tracking)
CREATE TABLE IF NOT EXISTS chain_creator_content_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    entity_type VARCHAR(32) NOT NULL,
    entity_id UUID NOT NULL,
    archived_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    restored_at TIMESTAMPTZ,
    UNIQUE(entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_creator_archive_profile ON chain_creator_content_archive(profile_id, archived_at DESC);

-- Creator contact info (business tools)
CREATE TABLE IF NOT EXISTS chain_creator_contact_info (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    contact_type VARCHAR(32) NOT NULL DEFAULT 'email',
    contact_value TEXT NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, contact_type)
);

-- Add columns to chain_profiles for business tools
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_profiles' AND column_name = 'business_category') THEN
        ALTER TABLE chain_profiles ADD COLUMN business_category VARCHAR(64) DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_profiles' AND column_name = 'contact_button_label') THEN
        ALTER TABLE chain_profiles ADD COLUMN contact_button_label VARCHAR(64) DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_profiles' AND column_name = 'contact_button_url') THEN
        ALTER TABLE chain_profiles ADD COLUMN contact_button_url TEXT DEFAULT '';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'chain_profiles' AND column_name = 'has_active_verified_badge') THEN
        ALTER TABLE chain_profiles ADD COLUMN has_active_verified_badge BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;
