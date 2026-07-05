-- RPromo (Reach Promotion) video feature
-- User A uploads promo videos; users B, C, D, E can view and like

CREATE TABLE IF NOT EXISTS chain_rpromo_videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT '',
    description TEXT DEFAULT '',
    video_url TEXT NOT NULL,
    thumbnail_url TEXT DEFAULT '',
    views_count INTEGER NOT NULL DEFAULT 0,
    likes_count INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rpromo_videos_profile_id ON chain_rpromo_videos(profile_id);
CREATE INDEX IF NOT EXISTS idx_rpromo_videos_created_at ON chain_rpromo_videos(created_at DESC);

CREATE TABLE IF NOT EXISTS chain_rpromo_likes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES chain_rpromo_videos(id) ON DELETE CASCADE,
    profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(video_id, profile_id)
);

CREATE INDEX IF NOT EXISTS idx_rpromo_likes_video_id ON chain_rpromo_likes(video_id);
CREATE INDEX IF NOT EXISTS idx_rpromo_likes_profile_id ON chain_rpromo_likes(profile_id);
