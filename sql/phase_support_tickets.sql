CREATE TABLE IF NOT EXISTS chain_support_faq_categories (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  slug VARCHAR(100) UNIQUE NOT NULL,
  description TEXT,
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_help_articles (
  id SERIAL PRIMARY KEY,
  category_id INTEGER REFERENCES chain_support_faq_categories(id) ON DELETE SET NULL,
  title VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE NOT NULL,
  content TEXT NOT NULL,
  is_published BOOLEAN DEFAULT FALSE,
  views INTEGER DEFAULT 0,
  helpful_count INTEGER DEFAULT 0,
  not_helpful_count INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_tickets (
  id SERIAL PRIMARY KEY,
  ticket_id VARCHAR(32) UNIQUE NOT NULL,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  subject VARCHAR(255) NOT NULL,
  category VARCHAR(64) NOT NULL,
  description TEXT NOT NULL,
  priority VARCHAR(16) NOT NULL DEFAULT 'medium',
  status VARCHAR(24) NOT NULL DEFAULT 'open',
  related_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  related_post_id INTEGER,
  related_reel_id INTEGER,
  related_story_id INTEGER,
  related_live_room_id INTEGER,
  related_message_id INTEGER,
  related_call_id INTEGER,
  related_order_id VARCHAR(64),
  related_transaction_id VARCHAR(64),
  evidence_json TEXT,
  assigned_to INTEGER REFERENCES chain_support_agents(id) ON DELETE SET NULL,
  escalated_to VARCHAR(32),
  escalated_at TIMESTAMPTZ,
  escalated_reason TEXT,
  resolved_at TIMESTAMPTZ,
  resolution_notes TEXT,
  reopened_count INTEGER DEFAULT 0,
  last_activity_at TIMESTAMPTZ DEFAULT NOW(),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_ticket_messages (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER NOT NULL REFERENCES chain_support_tickets(id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  is_agent BOOLEAN DEFAULT FALSE,
  message TEXT NOT NULL,
  is_internal_note BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_ticket_attachments (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER NOT NULL REFERENCES chain_support_tickets(id) ON DELETE CASCADE,
  message_id INTEGER REFERENCES chain_support_ticket_messages(id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  filename VARCHAR(255) NOT NULL,
  filepath VARCHAR(500) NOT NULL,
  file_size INTEGER DEFAULT 0,
  mime_type VARCHAR(100),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_ticket_events (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER NOT NULL REFERENCES chain_support_tickets(id) ON DELETE CASCADE,
  profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  agent_id INTEGER REFERENCES chain_support_agents(id) ON DELETE SET NULL,
  event_type VARCHAR(32) NOT NULL,
  field_name VARCHAR(64),
  old_value TEXT,
  new_value TEXT,
  reason TEXT,
  ip_address VARCHAR(45),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_agents (
  id SERIAL PRIMARY KEY,
  profile_id UUID UNIQUE NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  display_name VARCHAR(100) NOT NULL,
  role VARCHAR(32) NOT NULL DEFAULT 'agent',
  is_active BOOLEAN DEFAULT TRUE,
  max_assigned INTEGER DEFAULT 20,
  assigned_count INTEGER DEFAULT 0,
  last_active_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_agent_assignments (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER NOT NULL REFERENCES chain_support_tickets(id) ON DELETE CASCADE,
  agent_id INTEGER NOT NULL REFERENCES chain_support_agents(id) ON DELETE CASCADE,
  assigned_by UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  assigned_at TIMESTAMPTZ DEFAULT NOW(),
  unassigned_at TIMESTAMPTZ,
  reason VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS chain_support_feedback (
  id SERIAL PRIMARY KEY,
  ticket_id INTEGER UNIQUE NOT NULL REFERENCES chain_support_tickets(id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
  comment TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chain_support_saved_replies (
  id SERIAL PRIMARY KEY,
  agent_id INTEGER NOT NULL REFERENCES chain_support_agents(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  content TEXT NOT NULL,
  category VARCHAR(64),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_support_tickets_profile ON chain_support_tickets(profile_id);
CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON chain_support_tickets(status);
CREATE INDEX IF NOT EXISTS idx_support_tickets_category ON chain_support_tickets(category);
CREATE INDEX IF NOT EXISTS idx_support_tickets_priority ON chain_support_tickets(priority);
CREATE INDEX IF NOT EXISTS idx_support_tickets_assigned ON chain_support_tickets(assigned_to);
CREATE INDEX IF NOT EXISTS idx_support_tickets_last_activity ON chain_support_tickets(last_activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_support_ticket_messages_ticket ON chain_support_ticket_messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_support_ticket_events_ticket ON chain_support_ticket_events(ticket_id);
CREATE INDEX IF NOT EXISTS idx_support_ticket_events_type ON chain_support_ticket_events(event_type);
CREATE INDEX IF NOT EXISTS idx_support_articles_category ON chain_support_help_articles(category_id);
CREATE INDEX IF NOT EXISTS idx_support_articles_published ON chain_support_help_articles(is_published);
