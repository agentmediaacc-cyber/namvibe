ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS privacy_accepted BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS privacy_version TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS terms_version TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_message TEXT DEFAULT 'everyone';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_call TEXT DEFAULT 'everyone';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS who_can_see_status TEXT DEFAULT 'everyone';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS message_only_after_match BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS tour_seen BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_chain_profiles_auth_user_id ON chain_profiles(auth_user_id);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_username ON chain_profiles(username);
CREATE INDEX IF NOT EXISTS idx_chain_profiles_email ON chain_profiles(email);
