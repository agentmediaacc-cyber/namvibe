-- Phase 50: Production launch readiness, audits, alerts, backups.
-- Safe/idempotent migration for PostgreSQL/Neon.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS chain_deployment_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    audit_type TEXT NOT NULL,
    status TEXT NOT NULL,
    score INTEGER NOT NULL DEFAULT 0,
    findings JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_system_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component TEXT NOT NULL,
    severity TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    resolved BOOLEAN NOT NULL DEFAULT false,
    resolved_at TIMESTAMPTZ NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chain_backup_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backup_type TEXT NOT NULL,
    status TEXT NOT NULL,
    location TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chain_system_alerts_component ON chain_system_alerts(component);
CREATE INDEX IF NOT EXISTS idx_chain_system_alerts_severity ON chain_system_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_chain_system_alerts_resolved ON chain_system_alerts(resolved);
CREATE INDEX IF NOT EXISTS idx_chain_system_alerts_created_at ON chain_system_alerts(created_at);
CREATE INDEX IF NOT EXISTS idx_chain_deployment_audits_audit_type ON chain_deployment_audits(audit_type);
CREATE INDEX IF NOT EXISTS idx_chain_deployment_audits_created_at ON chain_deployment_audits(created_at);
CREATE INDEX IF NOT EXISTS idx_chain_backup_events_created_at ON chain_backup_events(created_at);
