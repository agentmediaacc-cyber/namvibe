-- Phase 69 — Realtime Communication Fix
-- Idempotent migration for messaging, calling, and notification tables.
-- All statements use IF NOT EXISTS / safe patterns.

-- =============================================================
-- 1. chain_messages: add missing columns (uses recipient_profile_id)
-- =============================================================
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS attachment_url TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS attachment_mime TEXT;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS attachment_size BIGINT DEFAULT 0;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS audio_duration INTEGER DEFAULT 0;
ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS forwarded_from_message_id UUID REFERENCES chain_messages(id) ON DELETE SET NULL;

-- =============================================================
-- 2. chain_thread_members: add missing columns
-- =============================================================
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_thread_members ADD COLUMN IF NOT EXISTS last_delivered_at TIMESTAMPTZ;

-- =============================================================
-- 3. chain_calls: add extra columns for full call lifecycle
-- =============================================================
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS ended_by_profile_id UUID REFERENCES chain_profiles(id);
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS ringing_started_at TIMESTAMPTZ;
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS missed_reason TEXT;
ALTER TABLE chain_calls ADD COLUMN IF NOT EXISTS block_reason TEXT;

-- =============================================================
-- 4. chain_call_participants: ensure participant tracking
-- =============================================================
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS connection_status TEXT DEFAULT 'connecting';
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS joined_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS left_at TIMESTAMPTZ;
ALTER TABLE chain_call_participants ADD COLUMN IF NOT EXISTS duration_seconds INTEGER DEFAULT 0;

-- =============================================================
-- 5. chain_notifications: add call event columns
-- =============================================================
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS actor_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS entity_type TEXT;
ALTER TABLE chain_notifications ADD COLUMN IF NOT EXISTS entity_id UUID;

-- =============================================================
-- 6. chain_blocks: ensure index for bidirectional lookup
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_chain_blocks_blocked
  ON chain_blocks(blocked_profile_id, blocker_profile_id)
  WHERE deleted_at IS NULL;

-- =============================================================
-- 7. Performance indexes for communication queries
-- =============================================================
CREATE INDEX IF NOT EXISTS idx_messages_thread_created
  ON chain_messages(thread_id, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_messages_sender_status
  ON chain_messages(sender_profile_id, delivery_status)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_messages_recipient_unread
  ON chain_messages(recipient_profile_id, thread_id, is_seen)
  WHERE deleted_at IS NULL AND recipient_profile_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_thread_members_profile
  ON chain_thread_members(profile_id, thread_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_thread_members_unread
  ON chain_thread_members(profile_id, last_read_at, thread_id)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_notifications_recipient_unread
  ON chain_notifications(recipient_profile_id, is_read, created_at DESC)
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_call_logs_profile
  ON chain_call_logs(profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_calls_receiver_status
  ON chain_calls(receiver_profile_id, status);

CREATE INDEX IF NOT EXISTS idx_push_tokens_active
  ON chain_push_tokens(profile_id, active)
  WHERE active = TRUE;

CREATE INDEX IF NOT EXISTS idx_reports_status
  ON chain_reports(status, created_at DESC);

-- =============================================================
-- 8. Ensure chain_call_logs exists (safe idempotent creation)
-- =============================================================
CREATE TABLE IF NOT EXISTS chain_call_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id UUID REFERENCES chain_calls(id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  other_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  direction TEXT DEFAULT 'outgoing',
  call_type TEXT DEFAULT 'audio',
  status TEXT DEFAULT 'missed',
  duration_seconds INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_call_logs_lookup
  ON chain_call_logs(profile_id, other_profile_id, created_at DESC);

-- =============================================================
-- 9. Ensure chain_notification_events safe idempotent creation
-- =============================================================
-- Add missing columns to chain_notification_events if table already exists
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS target_type TEXT;
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS target_id UUID;
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS action_url TEXT;
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS image_url TEXT;
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS priority TEXT DEFAULT 'normal';
ALTER TABLE chain_notification_events ADD COLUMN IF NOT EXISTS metadata JSONB DEFAULT '{}';

CREATE TABLE IF NOT EXISTS chain_notification_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
  actor_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
  event_type TEXT NOT NULL,
  title TEXT,
  body TEXT,
  target_type TEXT,
  target_id UUID,
  action_url TEXT,
  image_url TEXT,
  is_read BOOLEAN DEFAULT FALSE,
  is_deleted BOOLEAN DEFAULT FALSE,
  priority TEXT DEFAULT 'normal',
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now(),
  read_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_notification_events_profile
  ON chain_notification_events(profile_id, is_read, created_at DESC);

-- =============================================================
-- 10. Push tokens table (safe idempotent)
-- =============================================================
CREATE TABLE IF NOT EXISTS chain_push_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  device_session_id UUID,
  platform TEXT DEFAULT 'web',
  token TEXT NOT NULL DEFAULT '',
  active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_push_tokens_lookup
  ON chain_push_tokens(profile_id, platform, active)
  WHERE active = TRUE;

-- =============================================================
-- 11. Message receipt tracking (safe idempotent)
-- =============================================================
CREATE TABLE IF NOT EXISTS chain_message_receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID NOT NULL REFERENCES chain_messages(id) ON DELETE CASCADE,
  thread_id UUID NOT NULL REFERENCES chain_message_threads(id) ON DELETE CASCADE,
  profile_id UUID NOT NULL REFERENCES chain_profiles(id) ON DELETE CASCADE,
  delivered_at TIMESTAMPTZ,
  seen_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(message_id, profile_id)
);

CREATE INDEX IF NOT EXISTS idx_message_receipts_thread
  ON chain_message_receipts(thread_id, profile_id);
