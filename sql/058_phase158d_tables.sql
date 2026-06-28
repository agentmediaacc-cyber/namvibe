-- Verification documents
CREATE TABLE IF NOT EXISTS chain_verification_documents (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
    id_front_url TEXT,
    id_back_url TEXT,
    address_proof_url TEXT,
    address_proof_type TEXT DEFAULT 'water_bill',
    selfie_video_url TEXT,
    whatsapp_phone TEXT,
    whatsapp_code TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','needs_more_info')),
    admin_notes TEXT,
    reviewed_by UUID,
    reviewed_at TIMESTAMPTZ,
    submitted_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Ad campaigns
CREATE TABLE IF NOT EXISTS chain_ad_campaigns (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
    name TEXT,
    objective TEXT CHECK (objective IN ('reach','website_clicks','profile_visits','followers')),
    media_url TEXT,
    media_type TEXT DEFAULT 'image',
    target_audience JSONB DEFAULT '{}',
    budget NUMERIC(12,2) DEFAULT 0,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending','active','paused','completed','rejected')),
    impressions INT DEFAULT 0,
    clicks INT DEFAULT 0,
    reach INT DEFAULT 0,
    engagement INT DEFAULT 0,
    is_sponsored BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Subscriber content
CREATE TABLE IF NOT EXISTS chain_subscriber_content (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
    media_id UUID,
    content_type TEXT DEFAULT 'gallery' CHECK (content_type IN ('gallery','post','reel')),
    access_level TEXT DEFAULT 'subscribers' CHECK (access_level IN ('subscribers','followers','public','private')),
    thumbnail_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Trust signals
CREATE TABLE IF NOT EXISTS chain_trust_signals (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
    signal_type TEXT CHECK (signal_type IN ('possible_fake','suspicious_messaging','many_reports','duplicate_account','unusual_login','verified','new_account','high_trust')),
    score INT DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Business page opening hours
CREATE TABLE IF NOT EXISTS chain_business_hours (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE UNIQUE,
    hours JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Profile views tracking
CREATE TABLE IF NOT EXISTS chain_profile_views (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
    viewer_profile_id UUID REFERENCES chain_profiles(id) ON DELETE SET NULL,
    viewed_at TIMESTAMPTZ DEFAULT now()
);

-- Location sharing
CREATE TABLE IF NOT EXISTS chain_location_sharing (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE UNIQUE,
    is_sharing BOOLEAN DEFAULT FALSE,
    authorized_viewers JSONB DEFAULT '[]',
    latitude NUMERIC(10,7),
    longitude NUMERIC(10,7),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Add columns to chain_profiles
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS show_phone_publicly BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS show_email_publicly BOOLEAN DEFAULT FALSE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS show_location_publicly BOOLEAN DEFAULT TRUE;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verification_date TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_category TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_description TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_website TEXT;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_services JSONB DEFAULT '[]';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS business_products JSONB DEFAULT '[]';
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS completion_percentage INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS report_count INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS suspicious_score INT DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS account_trust_level TEXT DEFAULT 'new' CHECK (account_trust_level IN ('new','low','medium','high','verified'));
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS account_data_requested_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS account_delete_requested_at TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS last_password_change TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS last_email_change TIMESTAMPTZ;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS last_phone_change TIMESTAMPTZ;

-- Support reports
CREATE TABLE IF NOT EXISTS chain_support_reports (
    id UUID PRIMARY KEY,
    profile_id UUID REFERENCES chain_profiles(id) ON DELETE CASCADE,
    subject TEXT,
    message TEXT,
    status TEXT DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved','closed')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
