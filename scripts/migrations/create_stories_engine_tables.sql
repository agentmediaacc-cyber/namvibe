-- Stories 2.0 Engine Migration (FIXED: UUID types)
-- Run after verifying chain_status_posts exists

-- Story highlights
CREATE TABLE IF NOT EXISTS chain_story_highlights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title VARCHAR(64) NOT NULL DEFAULT 'Highlights',
    cover_url TEXT DEFAULT '',
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_story_highlights_profile ON chain_story_highlights(profile_id);
CREATE INDEX IF NOT EXISTS idx_story_highlights_sort ON chain_story_highlights(profile_id, sort_order);

-- Story highlight items
CREATE TABLE IF NOT EXISTS chain_story_highlight_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    highlight_id UUID NOT NULL REFERENCES chain_story_highlights(id) ON DELETE CASCADE,
    story_id UUID NOT NULL REFERENCES chain_status_posts(id) ON DELETE CASCADE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_story_highlight_items_highlight ON chain_story_highlight_items(highlight_id);
CREATE INDEX IF NOT EXISTS idx_story_highlight_items_story ON chain_story_highlight_items(story_id);

-- Story close friends list
CREATE TABLE IF NOT EXISTS chain_story_close_friends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    friend_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, friend_id)
);

CREATE INDEX IF NOT EXISTS idx_story_close_friends_profile ON chain_story_close_friends(profile_id);

-- Story hidden from users
CREATE TABLE IF NOT EXISTS chain_story_hidden_from (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    hidden_user_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(profile_id, hidden_user_id)
);

CREATE INDEX IF NOT EXISTS idx_story_hidden_from_profile ON chain_story_hidden_from(profile_id);

-- Story analytics events
CREATE TABLE IF NOT EXISTS chain_story_analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    story_id UUID NOT NULL REFERENCES chain_status_posts(id) ON DELETE CASCADE,
    viewer_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    event_type VARCHAR(32) NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_story_analytics_story ON chain_story_analytics_events(story_id);
CREATE INDEX IF NOT EXISTS idx_story_analytics_event ON chain_story_analytics_events(story_id, event_type);

-- Add columns to chain_status_posts if missing
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'mentions'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN mentions JSONB DEFAULT '[]';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'hashtags'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN hashtags JSONB DEFAULT '[]';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'link_url'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN link_url TEXT DEFAULT '';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'location_name'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN location_name TEXT DEFAULT '';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'reaction_count'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN reaction_count INTEGER NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'reply_count'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN reply_count INTEGER NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'forward_count'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN forward_count INTEGER NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'back_count'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN back_count INTEGER NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'exit_count'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN exit_count INTEGER NOT NULL DEFAULT 0;
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'chain_status_posts' AND column_name = 'completion_rate'
    ) THEN
        ALTER TABLE chain_status_posts ADD COLUMN completion_rate REAL DEFAULT 0;
    END IF;
END $$;
