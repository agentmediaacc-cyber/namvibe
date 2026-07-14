-- ============================================================
-- Connecting You — NamVibe Dating Program Schema
-- All mentor/event data is created by admin in the admin panel.
-- Assessment questions below are the system framework (not fake data).
-- ============================================================

-- Program Enrollments
CREATE TABLE IF NOT EXISTS chain_cy_enrollments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,

  relationship_goal VARCHAR(32) NOT NULL DEFAULT 'serious',
  -- serious, marriage, friendship, networking, business_partner

  religion VARCHAR(64) DEFAULT '',
  languages TEXT[] DEFAULT '{}',
  tribe VARCHAR(64) DEFAULT '',
  region VARCHAR(64) DEFAULT '',
  town VARCHAR(64) DEFAULT '',
  occupation VARCHAR(128) DEFAULT '',
  education VARCHAR(64) DEFAULT '',

  personality_type VARCHAR(16) DEFAULT '',
  -- introvert, extrovert, ambivert

  love_language VARCHAR(32) DEFAULT '',
  -- words_of_affirmation, acts_of_service, gifts, quality_time, physical_touch

  communication_style VARCHAR(32) DEFAULT '',
  -- direct, indirect, analytical, expressive

  faith_importance VARCHAR(16) DEFAULT '',
  -- none, low, medium, high, very_high

  wants_children VARCHAR(16) DEFAULT '',
  -- yes, no, maybe, already_have

  would_relocate VARCHAR(16) DEFAULT '',
  -- yes, no, maybe

  financial_habits VARCHAR(32) DEFAULT '',
  -- saver, spender, balanced,investor

  conflict_style VARCHAR(32) DEFAULT '',
  -- avoidant, confrontational, collaborative, compromising

  status VARCHAR(24) NOT NULL DEFAULT 'pending',
  -- pending, approved, active, suspended, withdrawn

  verified BOOLEAN DEFAULT FALSE,
  verified_at TIMESTAMPTZ,

  compatibility_score DECIMAL(5,2) DEFAULT 0,

  region_priority INTEGER DEFAULT 0,
  -- 0=normal, 1=featured, 2=top_pick

  enrolled_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(profile_id)
);

CREATE INDEX IF NOT EXISTS idx_cy_enroll_status ON chain_cy_enrollments(status);
CREATE INDEX IF NOT EXISTS idx_cy_enroll_region ON chain_cy_enrollments(region, status);
CREATE INDEX IF NOT EXISTS idx_cy_enroll_goal ON chain_cy_enrollments(relationship_goal, status);

-- Assessment Questions
CREATE TABLE IF NOT EXISTS chain_cy_assessment_questions (
  id SERIAL PRIMARY KEY,
  category VARCHAR(32) NOT NULL,
  -- conflict, values, lifestyle, future, communication, faith, finance
  question TEXT NOT NULL,
  options JSONB NOT NULL DEFAULT '[]',
  weight DECIMAL(3,2) DEFAULT 1.0,
  sort_order INTEGER DEFAULT 0,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Assessment Responses
CREATE TABLE IF NOT EXISTS chain_cy_assessment_responses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  question_id INTEGER NOT NULL REFERENCES chain_cy_assessment_questions(id),
  answer TEXT NOT NULL,
  answered_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(profile_id, question_id)
);

-- Compatibility Scores Between Pairs
CREATE TABLE IF NOT EXISTS chain_cy_compatibility (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_a UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  profile_b UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  overall_score DECIMAL(5,2) NOT NULL DEFAULT 0,
  category_scores JSONB DEFAULT '{}',
  -- {conflict: 85, values: 92, lifestyle: 78, ...}
  calculated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(profile_a, profile_b)
);

CREATE INDEX IF NOT EXISTS idx_cy_compat_a ON chain_cy_compatibility(profile_a, overall_score DESC);
CREATE INDEX IF NOT EXISTS idx_cy_compat_b ON chain_cy_compatibility(profile_b, overall_score DESC);

-- Live Events (Connecting You Live, Mentor Sessions, Meet-ups)
CREATE TABLE IF NOT EXISTS chain_cy_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type VARCHAR(32) NOT NULL,
  -- live_show, mentor_session, meet_up, speed_dating, balloon_pop
  title VARCHAR(255) NOT NULL,
  description TEXT DEFAULT '',
  host_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  mentor_id INTEGER REFERENCES chain_cy_mentors(id) ON DELETE SET NULL,

  region VARCHAR(64) DEFAULT 'all',
  max_participants INTEGER DEFAULT 0,
  current_participants INTEGER DEFAULT 0,

  event_date TIMESTAMPTZ NOT NULL,
  duration_minutes INTEGER DEFAULT 60,
  venue VARCHAR(255) DEFAULT '',
  venue_address TEXT DEFAULT '',
  is_virtual BOOLEAN DEFAULT TRUE,
  live_room_id INTEGER REFERENCES chain_live_rooms(id) ON DELETE SET NULL,

  status VARCHAR(24) DEFAULT 'scheduled',
  -- scheduled, live, completed, cancelled

  cover_image TEXT DEFAULT '',
  tags TEXT[] DEFAULT '{}',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cy_events_type ON chain_cy_events(event_type, status);
CREATE INDEX IF NOT EXISTS idx_cy_events_date ON chain_cy_events(event_date DESC);

-- Event Registrations
CREATE TABLE IF NOT EXISTS chain_cy_event_registrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES chain_cy_events(id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  status VARCHAR(24) DEFAULT 'registered',
  -- registered, attended, cancelled, waitlisted
  checked_in BOOLEAN DEFAULT FALSE,
  checked_in_at TIMESTAMPTZ,
  registered_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(event_id, profile_id)
);

-- Balloon Pop Records
CREATE TABLE IF NOT EXISTS chain_cy_balloon_pops (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id UUID NOT NULL REFERENCES chain_cy_events(id) ON DELETE CASCADE,
  popped_profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  popped_by_admin BOOLEAN DEFAULT TRUE,
  revealed_name VARCHAR(128) DEFAULT '',
  revealed_age INTEGER DEFAULT 0,
  revealed_region VARCHAR(64) DEFAULT '',
  revealed_interests TEXT[] DEFAULT '{}',
  interest_count INTEGER DEFAULT 0,
  popped_at TIMESTAMPTZ DEFAULT NOW()
);

-- Balloon Interest Expressions
CREATE TABLE IF NOT EXISTS chain_cy_balloon_interests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  balloon_pop_id UUID NOT NULL REFERENCES chain_cy_balloon_pops(id) ON DELETE CASCADE,
  expressor_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  status VARCHAR(24) DEFAULT 'pending',
  -- pending, accepted, declined, expired
  expressed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(balloon_pop_id, expressor_id)
);

-- Introductions (Admin Matchmaking)
CREATE TABLE IF NOT EXISTS chain_cy_introductions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_a UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  profile_b UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  compatibility_score DECIMAL(5,2) DEFAULT 0,
  admin_notes TEXT DEFAULT '',
  introduced_by UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,

  status VARCHAR(24) DEFAULT 'pending',
  -- pending, both_interested, introduced, matched, declined, expired

  a_response VARCHAR(16) DEFAULT 'pending',
  -- pending, accept, decline, maybe
  b_response VARCHAR(16) DEFAULT 'pending',

  introduced_at TIMESTAMPTZ DEFAULT NOW(),
  responded_at TIMESTAMPTZ,
  matched_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_cy_intro_status ON chain_cy_introductions(status);
CREATE INDEX IF NOT EXISTS idx_cy_intro_a ON chain_cy_introductions(profile_a, status);
CREATE INDEX IF NOT EXISTS idx_cy_intro_b ON chain_cy_introductions(profile_b, status);

-- Successful Matches
CREATE TABLE IF NOT EXISTS chain_cy_matches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_a UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  profile_b UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  introduction_id UUID REFERENCES chain_cy_introductions(id) ON DELETE SET NULL,
  chat_room_id UUID,
  match_date TIMESTAMPTZ DEFAULT NOW(),
  status VARCHAR(24) DEFAULT 'active',
  -- active, ended, married, featured
  UNIQUE(profile_a, profile_b)
);

-- Success Stories
CREATE TABLE IF NOT EXISTS chain_cy_success_stories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  couple_names VARCHAR(255) NOT NULL,
  region VARCHAR(64) DEFAULT '',
  story TEXT NOT NULL,
  photo_urls TEXT[] DEFAULT '{}',
  wedding_photo_url TEXT DEFAULT '',
  is_featured BOOLEAN DEFAULT FALSE,
  is_public BOOLEAN DEFAULT TRUE,
  submitted_by UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  submitted_at TIMESTAMPTZ DEFAULT NOW()
);

-- Mentors
CREATE TABLE IF NOT EXISTS chain_cy_mentors (
  id SERIAL PRIMARY KEY,
  profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  name VARCHAR(128) NOT NULL,
  title VARCHAR(128) DEFAULT '',
  specialty VARCHAR(128) DEFAULT '',
  bio TEXT DEFAULT '',
  avatar_url TEXT DEFAULT '',
  is_active BOOLEAN DEFAULT TRUE,
  session_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Announcements
CREATE TABLE IF NOT EXISTS chain_cy_announcements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title VARCHAR(255) NOT NULL,
  body TEXT NOT NULL,
  audience VARCHAR(32) DEFAULT 'all',
  -- all, enrolled, verified, region
  region VARCHAR(64) DEFAULT '',
  priority VARCHAR(16) DEFAULT 'normal',
  -- normal, high, urgent
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- Seed: Assessment Questions
-- ============================================================
INSERT INTO chain_cy_assessment_questions (category, question, options, weight, sort_order) VALUES
('conflict', 'How do you handle conflict in a relationship?', '["Talk it out calmly", "Need time alone first", "Seek a mediator", "Address it immediately"]', 1.5, 1),
('values', 'Do you want children?', '["Yes, definitely", "Open to it", "No, not for me", "Already have children"]', 1.3, 2),
('lifestyle', 'Would you relocate for love?', '["Yes, anywhere", "Within my country", "Only to a bigger city", "No, my roots are here"]', 1.0, 3),
('lifestyle', 'Are you more of an introvert or extrovert?', '["Introvert", "Extrovert", "Ambivert", "Depends on the situation"]', 0.8, 4),
('finance', 'What are your financial habits?', '["Saver — I plan ahead", "Spender — I enjoy life now", "Balanced — best of both", "Investor — building wealth"]', 1.2, 5),
('communication', 'What is your love language?', '["Words of affirmation", "Acts of service", "Receiving gifts", "Quality time", "Physical touch"]', 1.4, 6),
('communication', 'How would you describe your communication style?', '["Direct and honest", "Thoughtful and measured", "Expressive and emotional", "Logical and analytical"]', 1.1, 7),
('faith', 'How important is faith/religion in your life?', '["Very important — central to my life", "Important — guides my values", "Somewhat — spiritual but flexible", "Not important — not a factor"]', 1.0, 8),
('future', 'Where do you see yourself in 5 years?', '["Married with family", "Career-focused and independent", "Traveling the world", "Building a business", "Growing in my community"]', 1.0, 9),
('conflict', 'How do you handle financial decisions as a couple?', '["Joint everything", "Split bills equally", "Each handles their own", "Proportional to income"]', 1.0, 10),
('values', 'What matters most in a partner?', '["Honesty and trust", "Ambition and drive", "Kindness and empathy", "Sense of humor", "Shared values and faith"]', 1.5, 11),
('lifestyle', 'What does your ideal weekend look like?', '["Outdoor adventure", "Cozy night in", "Social events and friends", "Working on personal projects", "Family time"]', 0.7, 12),
('communication', 'How do you prefer to resolve disagreements?', '["Face-to-face conversation", "Text/message first", "Give it time then discuss", "Never go to bed angry"]', 1.0, 13),
('future', 'How important is marriage to you?', '["Essential — a life goal", "Important but not urgent", "Open to it", "Not interested in marriage"]', 1.3, 14),
('faith', 'Would you date someone of a different religion?', '["Yes, absolutely", "Open to it", "Prefer same faith", "It depends on the person"]', 0.9, 15);
