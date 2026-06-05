-- CHAIN PHASE 12 SCHEMA UPDATES

-- 1. Push Notification Devices
CREATE TABLE IF NOT EXISTS chain_push_devices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    device_token text NOT NULL,
    platform text NOT NULL, -- android, ios, web
    app_version text,
    last_seen_at timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE(profile_id, device_token)
);
CREATE INDEX IF NOT EXISTS idx_push_devices_profile ON chain_push_devices(profile_id) WHERE deleted_at IS NULL;

-- 2. Security & Bot Detection
CREATE TABLE IF NOT EXISTS chain_login_history (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    ip_address inet,
    user_agent text,
    device_fingerprint text,
    location_data jsonb,
    is_anomaly boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_login_history_profile_ip ON chain_login_history(profile_id, ip_address);

CREATE TABLE IF NOT EXISTS chain_ip_reputation (
    ip_address inet PRIMARY KEY,
    trust_score numeric(4,2) DEFAULT 5.0,
    is_blocked boolean DEFAULT false,
    last_seen_at timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now()
);

-- 3. Structured Logging & Tracing (Internal use, but table for persistent metrics)
CREATE TABLE IF NOT EXISTS chain_performance_logs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_path text,
    method text,
    status_code integer,
    latency_ms numeric,
    profile_id uuid,
    created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_perf_logs_path_latency ON chain_performance_logs(request_path, latency_ms DESC);

-- 4. Terms and Policies Versioning
CREATE TABLE IF NOT EXISTS chain_legal_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_type text NOT NULL, -- privacy_policy, terms_of_service, community_guidelines
    version text NOT NULL,
    content text NOT NULL,
    is_active boolean DEFAULT false,
    created_at timestamptz DEFAULT now()
);
