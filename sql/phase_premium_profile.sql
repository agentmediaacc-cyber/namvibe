-- ============================================================
-- PHASE: Premium Profile — SQL for all new profile features
-- Heavy data → Supabase (chain_achievements, collections, etc.)
-- Lite data → Neon (chain_presence, chain_visitors, etc.)
-- ============================================================

-- 1. ACHIEVEMENTS (Supabase — heavy, user-owned)
CREATE TABLE IF NOT EXISTS chain_achievements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  badge_key TEXT NOT NULL,
  badge_label TEXT NOT NULL,
  badge_icon TEXT NOT NULL DEFAULT '🏆',
  badge_color TEXT DEFAULT '#ec4899',
  description TEXT,
  unlocked_at TIMESTAMPTZ DEFAULT now(),
  is_featured BOOLEAN DEFAULT false,
  metadata JSONB DEFAULT '{}',
  UNIQUE(profile_id, badge_key)
);
CREATE INDEX IF NOT EXISTS idx_achievements_profile ON chain_achievements(profile_id);

-- 2. COLLECTIONS (Supabase)
CREATE TABLE IF NOT EXISTS chain_collections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  cover_url TEXT,
  is_public BOOLEAN DEFAULT true,
  is_hidden BOOLEAN DEFAULT false,
  sort_order INT DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_collections_profile ON chain_collections(profile_id);

-- 2b. Collection items (posts, reels, media in a collection)
CREATE TABLE IF NOT EXISTS chain_collection_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collection_id UUID NOT NULL REFERENCES chain_collections(id) ON DELETE CASCADE,
  item_type TEXT NOT NULL CHECK(item_type IN ('post','reel','story','photo','video','audio','document')),
  item_id UUID NOT NULL,
  added_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(collection_id, item_type, item_id)
);
CREATE INDEX IF NOT EXISTS idx_collection_items_collection ON chain_collection_items(collection_id);

-- 3. EDUCATION (Neon — lite)
CREATE TABLE IF NOT EXISTS chain_education (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  institution TEXT NOT NULL,
  degree TEXT,
  field_of_study TEXT,
  start_year INT,
  end_year INT,
  is_current BOOLEAN DEFAULT false,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_education_profile ON chain_education(profile_id);

-- 4. WORK EXPERIENCE (Neon)
CREATE TABLE IF NOT EXISTS chain_work_experience (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  company TEXT NOT NULL,
  position TEXT NOT NULL,
  location TEXT,
  start_year INT,
  end_year INT,
  is_current BOOLEAN DEFAULT false,
  description TEXT,
  company_logo_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_work_profile ON chain_work_experience(profile_id);

-- 5. USER SKILLS (Neon)
CREATE TABLE IF NOT EXISTS chain_user_skills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  skill_name TEXT NOT NULL,
  category TEXT DEFAULT 'general',
  proficiency INT DEFAULT 50 CHECK(proficiency >= 0 AND proficiency <= 100),
  is_top BOOLEAN DEFAULT false,
  UNIQUE(profile_id, skill_name)
);
CREATE INDEX IF NOT EXISTS idx_skills_profile ON chain_user_skills(profile_id);

-- 6. PROFILE VISITORS (Neon — lite, high-write)
CREATE TABLE IF NOT EXISTS chain_profile_visitors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  visitor_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  visited_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(profile_id, visitor_id)
);
CREATE INDEX IF NOT EXISTS idx_visitors_profile ON chain_profile_visitors(profile_id);
CREATE INDEX IF NOT EXISTS idx_visitors_visited_at ON chain_profile_visitors(visited_at DESC);

-- 7. PROFILE TIMELINE / MILESTONES (Supabase — user history)
CREATE TABLE IF NOT EXISTS chain_profile_timeline (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  event_type TEXT NOT NULL,
  event_label TEXT NOT NULL,
  event_icon TEXT DEFAULT '📌',
  event_date DATE,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_timeline_profile ON chain_profile_timeline(profile_id);

-- 8. PROFILE BADGES (Supabase)
CREATE TABLE IF NOT EXISTS chain_profile_badges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  badge_type TEXT NOT NULL,
  badge_label TEXT NOT NULL,
  badge_icon TEXT,
  badge_color TEXT DEFAULT '#ec4899',
  is_visible BOOLEAN DEFAULT true,
  earned_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(profile_id, badge_type)
);
CREATE INDEX IF NOT EXISTS idx_badges_profile ON chain_profile_badges(profile_id);

-- 9. USER ACTIVITY LOG (Neon — lite, temporal)
CREATE TABLE IF NOT EXISTS chain_activity_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  activity_type TEXT NOT NULL,
  activity_label TEXT,
  target_type TEXT,
  target_id UUID,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_log_profile ON chain_activity_log(profile_id);
CREATE INDEX IF NOT EXISTS idx_activity_log_created ON chain_activity_log(created_at DESC);

-- 10. COLLECTION FAVORITES (Neon — lite)
CREATE TABLE IF NOT EXISTS chain_user_favorites (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  favorite_type TEXT NOT NULL CHECK(favorite_type IN ('music','game','artist','place','food','book','movie','sport')),
  favorite_value TEXT NOT NULL,
  label TEXT,
  sort_order INT DEFAULT 0,
  UNIQUE(profile_id, favorite_type, favorite_value)
);
CREATE INDEX IF NOT EXISTS idx_favorites_profile ON chain_user_favorites(profile_id);

-- Existing chain_profiles additions for premium profile features
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS pronouns TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS occupation TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS company TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS school TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS university TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS mood_emoji TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS mood_text TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS current_activity TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS quote_of_day TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS activity_status TEXT DEFAULT 'online';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_score INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_level TEXT DEFAULT 'Bronze';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS member_since TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS country_flag TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS city_name TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS premium_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS creator_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS government_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS ngo_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS student_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS medical_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS teacher_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS trust_score INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS community_rating DECIMAL(3,2) DEFAULT 0.00;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS friendliness_score INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS safety_score INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS response_rate INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS response_time TEXT DEFAULT '';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS popularity_score INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS activity_level INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS scam_protection BOOLEAN DEFAULT true;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS identity_verified BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_theme TEXT DEFAULT 'default';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS local_time TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS weather_emoji TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS weather_temp TEXT;

-- Profile view count tracking
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_profile_views INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_post_likes INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_comments INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_shares INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_bookmarks INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_achievements INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_collections INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_albums INT DEFAULT 0;
