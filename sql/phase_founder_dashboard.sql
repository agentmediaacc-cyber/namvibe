-- phase_founder_dashboard.sql
-- Founder system tables for NamVibe system dashboard.
-- This migration is additive and non-destructive.
-- Run once against the target database.

CREATE TABLE chain_founder (
    id BIGSERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(200) DEFAULT '',
    email VARCHAR(255) DEFAULT '',
    phone VARCHAR(50) DEFAULT '',
    is_first_login BOOLEAN DEFAULT TRUE,
    must_change_password BOOLEAN DEFAULT TRUE,
    two_factor_enabled BOOLEAN DEFAULT FALSE,
    two_factor_secret VARCHAR(255) DEFAULT '',
    avatar_url VARCHAR(500) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    CONSTRAINT chain_founder_password_hash_length CHECK (char_length(password_hash) >= 40)
);

-- Index for fast founder lookup by username
CREATE INDEX idx_chain_founder_username ON chain_founder (username);

-- Index for fast founder lookup by id
CREATE INDEX idx_chain_founder_id ON chain_founder (id);

-- No founder account is seeded by default.
-- The founder must be created via a secure one-time bootstrap command
-- using environment-provided credentials.
--
-- To create the initial founder, run:
--   python3 scripts/bootstrap_founder.py
--
-- This script reads credentials from environment variables:
--   FOUNDER_USERNAME (default: kaser)
--   FOUNDER_PASSWORD (required, min 12 chars)
--
-- The bootstrap script generates a secure password hash and inserts
-- the founder record with must_change_password=TRUE, forcing a
-- password change on first login.
--
-- If you need to re-seed the password for an existing founder, use:
--   python3 -c "
-- import os; os.environ['CHAIN_DISABLE_DB_PING']='1'; os.environ['CHAIN_FAST_LOCAL']='1'; os.environ['CHAIN_DISABLE_PREWARM']='1'
-- from services.neon_service import prime_neon_runtime, execute
-- from werkzeug.security import generate_password_hash
-- prime_neon_runtime()
-- h = generate_password_hash('your-new-password', method='pbkdf2:sha256')
-- execute(\"UPDATE chain_founder SET password_hash=%s, must_change_password=TRUE, is_first_login=TRUE, full_name='', email='', phone='' WHERE username='kaser'\", (h,), timeout_ms=30000)
-- print('Done')
-- "
