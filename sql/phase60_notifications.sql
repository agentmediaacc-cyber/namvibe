-- Phase 60 — Premium Notification Center
-- Idempotent schema for chain_notifications and chain_notification_preferences

CREATE TABLE IF NOT EXISTS chain_notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    notification_type text NOT NULL,
    title text NOT NULL DEFAULT '',
    body text DEFAULT '',
    preview text,
    target_type text,
    target_id uuid,
    action_url text,
    image_url text,
    is_read boolean DEFAULT false,
    is_deleted boolean DEFAULT false,
    priority text DEFAULT 'normal',
    metadata jsonb DEFAULT '{}'::jsonb,
    created_at timestamptz DEFAULT now(),
    read_at timestamptz,
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS chain_notification_preferences (
    profile_id uuid PRIMARY KEY REFERENCES chain_profiles(id) ON DELETE CASCADE,
    in_app_enabled boolean DEFAULT true,
    push_enabled boolean DEFAULT true,
    email_enabled boolean DEFAULT false,
    sms_enabled boolean DEFAULT false,
    muted_types text[] DEFAULT '{}',
    quiet_hours_enabled boolean DEFAULT false,
    quiet_hours_start text,
    quiet_hours_end text,
    updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_notifications_recipient_unread
    ON chain_notifications (recipient_profile_id, is_read, created_at DESC)
    WHERE is_deleted = false;

CREATE INDEX IF NOT EXISTS idx_chain_notifications_recipient_created
    ON chain_notifications (recipient_profile_id, created_at DESC)
    WHERE is_deleted = false;

CREATE INDEX IF NOT EXISTS idx_chain_notifications_type
    ON chain_notifications (notification_type, created_at DESC)
    WHERE is_deleted = false;

CREATE INDEX IF NOT EXISTS idx_chain_notifications_target
    ON chain_notifications (target_type, target_id)
    WHERE target_id IS NOT NULL;
