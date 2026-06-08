ALTER TABLE chain_profiles
ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ;

ALTER TABLE chain_profiles
ADD COLUMN IF NOT EXISTS privacy_accepted BOOLEAN DEFAULT FALSE;

ALTER TABLE chain_profiles
ADD COLUMN IF NOT EXISTS terms_version TEXT;

ALTER TABLE chain_profiles
ADD COLUMN IF NOT EXISTS privacy_version TEXT;
