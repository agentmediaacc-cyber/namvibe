-- ============================================================
-- PHASE: All 26 Profile Features — Column additions & seed data
-- Run this migration to ensure all features have backing columns
-- ============================================================

-- Additional profile columns for the 26 feature set
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cover_video_url TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS nationality TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verified_id BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS driving_licence BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS student_card BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS employee_card BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS health_card BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_licence BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS professional_membership BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS volunteer_badge BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS favorite_songs JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS recently_played JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS playlists JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS favorite_artists JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS favorite_games JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS gaming_level TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS gaming_achievements JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS countries_visited JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS cities_visited JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS travel_wishlist JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_steps INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_workouts INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_cycling INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_running INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_calories INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_goals TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS fitness_sleep TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS marketplace_items_selling INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS marketplace_wishlist INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS marketplace_purchased INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS marketplace_reviews INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS wallet_rewards INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS wallet_tips INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS wallet_revenue INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS subscribers_count INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS subscriptions_count INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_downloads INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_live_hours INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_voice_calls INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_video_calls INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_messages INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_earnings NUMERIC DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS total_marketplace_sales INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS ai_profile_summary TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS ai_bio_suggestions JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS ai_friend_suggestions JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS ai_creator_recommendations JSONB DEFAULT '[]'::jsonb;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS ai_growth_analysis TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_booking_url TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_appointments_enabled BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_delivery_enabled BOOLEAN DEFAULT false;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_catalogue JSONB DEFAULT '[]'::jsonb;
