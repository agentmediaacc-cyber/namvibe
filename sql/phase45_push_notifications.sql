-- ============================================================
-- PHASE 45: Push Notifications, Background Calls, APNS, FCM, CallKit
-- Idempotent -- safe to re-run
-- ============================================================

-- 1. chain_push_tokens
CREATE TABLE IF NOT EXISTS chain_push_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    device_session_id UUID DEFAULT NULL,
    platform TEXT NOT NULL DEFAULT 'web',
    token TEXT NOT NULL DEFAULT '',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_push_tokens_profile ON chain_push_tokens(profile_id);
CREATE INDEX IF NOT EXISTS idx_push_tokens_platform ON chain_push_tokens(platform);
CREATE INDEX IF NOT EXISTS idx_push_tokens_active ON chain_push_tokens(active);
CREATE INDEX IF NOT EXISTS idx_push_tokens_token ON chain_push_tokens(token);

-- 2. chain_notification_queue
CREATE TABLE IF NOT EXISTS chain_notification_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    notification_type TEXT NOT NULL DEFAULT 'info',
    title TEXT NOT NULL DEFAULT '',
    body TEXT NOT NULL DEFAULT '',
    payload JSONB DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT now(),
    processed_at TIMESTAMPTZ DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_notif_queue_profile ON chain_notification_queue(profile_id);
CREATE INDEX IF NOT EXISTS idx_notif_queue_status ON chain_notification_queue(status);
CREATE INDEX IF NOT EXISTS idx_notif_queue_created ON chain_notification_queue(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notif_queue_type ON chain_notification_queue(notification_type);

-- 3. chain_notification_logs
CREATE TABLE IF NOT EXISTS chain_notification_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID NOT NULL,
    notification_type TEXT NOT NULL DEFAULT 'info',
    platform TEXT NOT NULL DEFAULT 'web',
    status TEXT NOT NULL DEFAULT 'sent',
    provider_response TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_notif_logs_profile ON chain_notification_logs(profile_id);
CREATE INDEX IF NOT EXISTS idx_notif_logs_type ON chain_notification_logs(notification_type);
CREATE INDEX IF NOT EXISTS idx_notif_logs_platform ON chain_notification_logs(platform);
CREATE INDEX IF NOT EXISTS idx_notif_logs_status ON chain_notification_logs(status);
CREATE INDEX IF NOT EXISTS idx_notif_logs_created ON chain_notification_logs(created_at DESC);

-- 4. chain_notification_preferences (idempotent migration)
ALTER TABLE chain_notification_preferences ADD COLUMN IF NOT EXISTS mentions BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_notification_preferences ADD COLUMN IF NOT EXISTS marketing BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_notification_preferences ADD COLUMN IF NOT EXISTS security_alerts BOOLEAN DEFAULT TRUE;

-- 5. Add notification_settings column to chain_profiles if not present
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS notification_settings JSONB DEFAULT '{}'::jsonb;
