-- Phase 49: Enterprise scaling, background jobs, workers, scheduler, health.
-- Safe/idempotent migration for Neon/PostgreSQL.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS chain_background_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 5,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    locked_by TEXT NULL,
    locked_at TIMESTAMPTZ NULL,
    run_after TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_job_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NULL,
    job_type TEXT NOT NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_scheduled_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name TEXT UNIQUE NOT NULL,
    job_type TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    interval_seconds INTEGER NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT true,
    last_run_at TIMESTAMPTZ NULL,
    next_run_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_worker_heartbeats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    worker_name TEXT UNIQUE NOT NULL,
    worker_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'online',
    current_job_id UUID NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_system_health_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component TEXT NOT NULL,
    status TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_status ON chain_background_jobs(status);
CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_job_type ON chain_background_jobs(job_type);
CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_priority ON chain_background_jobs(priority);
CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_run_after ON chain_background_jobs(run_after);
CREATE INDEX IF NOT EXISTS idx_chain_background_jobs_locked_at ON chain_background_jobs(locked_at);
CREATE INDEX IF NOT EXISTS idx_chain_job_logs_job_id ON chain_job_logs(job_id);
CREATE INDEX IF NOT EXISTS idx_chain_job_logs_job_type ON chain_job_logs(job_type);
CREATE INDEX IF NOT EXISTS idx_chain_scheduled_tasks_enabled ON chain_scheduled_tasks(enabled);
CREATE INDEX IF NOT EXISTS idx_chain_scheduled_tasks_next_run_at ON chain_scheduled_tasks(next_run_at);
CREATE INDEX IF NOT EXISTS idx_chain_worker_heartbeats_worker_name ON chain_worker_heartbeats(worker_name);
CREATE INDEX IF NOT EXISTS idx_chain_worker_heartbeats_last_seen_at ON chain_worker_heartbeats(last_seen_at);
CREATE INDEX IF NOT EXISTS idx_chain_system_health_events_component ON chain_system_health_events(component);
CREATE INDEX IF NOT EXISTS idx_chain_system_health_events_status ON chain_system_health_events(status);
CREATE INDEX IF NOT EXISTS idx_chain_system_health_events_created_at ON chain_system_health_events(created_at);

INSERT INTO chain_scheduled_tasks (task_name, job_type, schedule_type, interval_seconds, payload, enabled, next_run_at)
VALUES
    ('call_timeouts', 'call_timeout_check', 'interval', 30, '{}'::jsonb, true, now()),
    ('notification_delivery', 'notification_delivery', 'interval', 15, '{}'::jsonb, true, now()),
    ('safety_scans', 'safety_scan', 'interval', 60, '{}'::jsonb, true, now()),
    ('payout_review', 'payout_review', 'interval', 300, '{}'::jsonb, true, now()),
    ('media_cleanup', 'media_cleanup', 'interval', 3600, '{}'::jsonb, true, now()),
    ('trust_score_recalculation', 'trust_score_recalculation', 'interval', 600, '{}'::jsonb, true, now())
ON CONFLICT (task_name) DO UPDATE SET
    job_type = EXCLUDED.job_type,
    schedule_type = EXCLUDED.schedule_type,
    interval_seconds = EXCLUDED.interval_seconds,
    updated_at = now();
