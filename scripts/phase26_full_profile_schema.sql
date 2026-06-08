ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS normalized_email TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS normalized_phone TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS age INTEGER;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS current_country TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS country TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS country_of_birth TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS current_residential_location TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS location TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS city TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS preferred_language TEXT;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS avatar_upload_id TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_photo TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_upload_id TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_video_url TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS video_intro_url TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS storage_bucket TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS storage_path TEXT;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS interests JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS activities JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS looking_for JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS languages JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]'::jsonb;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS relationship_status TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS relationship_goal TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS account_type TEXT DEFAULT 'personal';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_type TEXT DEFAULT 'personal';

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS visibility TEXT DEFAULT 'public';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_visibility TEXT DEFAULT 'public';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verified BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_online BOOLEAN DEFAULT FALSE;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_messages BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_dating BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_gifts BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_zodiac_display BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS allow_birthday_notifications BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS show_zodiac BOOLEAN DEFAULT TRUE;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS creator_mode_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS seller_mode_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS dating_mode_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS premium_mode_enabled BOOLEAN DEFAULT FALSE;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS posts_count INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS reels_count INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS live_rooms_count INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS followers_count INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS following_count INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_views INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_likes INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS wallet_balance NUMERIC DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_completion INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS chain_score INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS trust_score INTEGER DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS rank TEXT;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS is_premium BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS premium_tier TEXT;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS website TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS pronouns TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS profile_theme TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS portfolio_url TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS portfolio_projects JSONB DEFAULT '[]'::jsonb;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_name TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_website TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_opening_hours JSONB DEFAULT '{}'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_location_data JSONB DEFAULT '{}'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_services JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_products JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_contact_email TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_contact_phone TEXT;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS password_set BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS auth_provider TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS provider_user_id TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS linked_providers JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS oauth_metadata JSONB DEFAULT '{}'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS username_slug TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS login_count INTEGER DEFAULT 0;

ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS zodiac_sign TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS terms_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS human_confirmed BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS anonymous_profile BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS account_mode TEXT DEFAULT 'standard';

CREATE INDEX IF NOT EXISTS idx_chain_profiles_auth_user_id ON chain_profiles(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_username ON chain_profiles(username);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_email ON chain_profiles(email);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_deleted_at ON chain_profiles(deleted_at);
