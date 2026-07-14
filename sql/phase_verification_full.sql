-- Phase: Full Identity Verification System
-- Multi-step verification: country → document type → upload → selfie → admin review

-- 1. Verification requests (enhanced)
CREATE TABLE IF NOT EXISTS chain_verification_requests_v2 (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
    verification_level integer DEFAULT 2,
    
    -- Step 1: Country & document selection
    country text,
    document_type text,       -- national_id, passport, drivers_licence, residence_permit, refugee_travel
    
    -- Step 2: Document images
    doc_front_url text,
    doc_back_url text,
    
    -- Step 3: Selfie
    selfie_url text,
    liveness_data jsonb,      -- {look_straight: bool, turn_left: bool, turn_right: bool, blink: bool, smile: bool}
    face_match_score numeric, -- 0-100
    
    -- Step 4: Auto-checks results
    auto_checks jsonb,        -- {expiry_valid: bool, format_valid: bool, name_consistent: bool, dob_match: bool, security_features: bool, duplicate_doc: bool, duplicate_face: bool, blacklist: bool}
    risk_indicators jsonb,    -- array of risk flags
    
    -- Step 5: Admin review
    status text DEFAULT 'pending',  -- pending, approved, rejected, needs_review, needs_more_info, suspended
    admin_notes text,
    rejection_reason text,
    reviewed_by uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    reviewed_at timestamptz,
    
    -- Metadata
    previous_attempts integer DEFAULT 0,
    previous_request_id uuid,  -- for re-submissions
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    deleted_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_vrfy2_profile_status ON chain_verification_requests_v2(profile_id, status);
CREATE INDEX IF NOT EXISTS idx_vrfy2_status ON chain_verification_requests_v2(status);
CREATE INDEX IF NOT EXISTS idx_vrfy2_country ON chain_verification_requests_v2(country);

-- 2. Verification levels
CREATE TABLE IF NOT EXISTS chain_verification_levels (
    id serial PRIMARY KEY,
    level integer UNIQUE NOT NULL,
    name text NOT NULL,
    description text,
    badge_color text DEFAULT '#1d9bf0',
    badge_icon text DEFAULT 'check-circle'
);

INSERT INTO chain_verification_levels (level, name, description, badge_color, badge_icon) VALUES
    (0, 'Email Verified', 'Email address confirmed', '#6b7280', 'envelope'),
    (1, 'Phone Verified', 'Phone number confirmed', '#9ca3af', 'phone'),
    (2, 'Identity Verified', 'Government ID + selfie verified', '#1d9bf0', 'check-circle'),
    (3, 'Creator Verified', 'Verified content creator', '#ec4899', 'star'),
    (4, 'Business Verified', 'Registered business verified', '#f59e0b', 'briefcase'),
    (5, 'Government Verified', 'Government or organization verified', '#10b981', 'building'),
    (6, 'Healthcare Verified', 'Healthcare professional verified', '#ef4444', 'heart-pulse')
ON CONFLICT (level) DO NOTHING;

-- 3. Country document rules (which docs are accepted per country)
CREATE TABLE IF NOT EXISTS chain_verification_country_rules (
    id serial PRIMARY KEY,
    country text NOT NULL,
    country_code text,
    accepted_docs text[] DEFAULT '{}',      -- document types accepted
    requires_back_photo boolean DEFAULT true,
    requires_residence_permit boolean DEFAULT false,
    notes text,
    created_at timestamptz DEFAULT now()
);

INSERT INTO chain_verification_country_rules (country, country_code, accepted_docs, requires_back_photo) VALUES
    ('Afghanistan', 'AF', '{national_id,passport}', false),
    ('Albania', 'AL', '{national_id,passport,drivers_licence}', true),
    ('Algeria', 'DZ', '{national_id,passport,drivers_licence}', true),
    ('Andorra', 'AD', '{national_id,passport}', false),
    ('Angola', 'AO', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Antigua and Barbuda', 'AG', '{passport,drivers_licence}', false),
    ('Argentina', 'AR', '{national_id,passport,drivers_licence}', true),
    ('Armenia', 'AM', '{national_id,passport}', false),
    ('Australia', 'AU', '{passport,drivers_licence,residence_permit}', true),
    ('Austria', 'AT', '{national_id,passport,drivers_licence}', true),
    ('Azerbaijan', 'AZ', '{national_id,passport}', false),
    ('Bahamas', 'BS', '{passport,drivers_licence}', false),
    ('Bahrain', 'BH', '{national_id,passport}', false),
    ('Bangladesh', 'BD', '{national_id,passport,drivers_licence}', true),
    ('Barbados', 'BB', '{passport,drivers_licence}', false),
    ('Belarus', 'BY', '{national_id,passport}', false),
    ('Belgium', 'BE', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Belize', 'BZ', '{national_id,passport,drivers_licence}', true),
    ('Benin', 'BJ', '{national_id,passport}', false),
    ('Bhutan', 'BT', '{national_id,passport}', false),
    ('Bolivia', 'BO', '{national_id,passport,drivers_licence}', true),
    ('Bosnia and Herzegovina', 'BA', '{national_id,passport,drivers_licence}', true),
    ('Botswana', 'BW', '{national_id,passport,drivers_licence}', true),
    ('Brazil', 'BR', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Brunei', 'BN', '{national_id,passport}', false),
    ('Bulgaria', 'BG', '{national_id,passport,drivers_licence}', true),
    ('Burkina Faso', 'BF', '{national_id,passport}', false),
    ('Burundi', 'BI', '{national_id,passport}', false),
    ('Cabo Verde', 'CV', '{national_id,passport}', false),
    ('Cambodia', 'KH', '{national_id,passport,drivers_licence}', true),
    ('Cameroon', 'CM', '{national_id,passport}', false),
    ('Canada', 'CA', '{passport,drivers_licence,residence_permit}', true),
    ('Central African Republic', 'CF', '{national_id,passport}', false),
    ('Chad', 'TD', '{national_id,passport}', false),
    ('Chile', 'CL', '{national_id,passport,drivers_licence}', true),
    ('China', 'CN', '{national_id,passport,residence_permit}', true),
    ('Colombia', 'CO', '{national_id,passport,drivers_licence}', true),
    ('Comoros', 'KM', '{national_id,passport}', false),
    ('Congo', 'CG', '{national_id,passport}', false),
    ('Costa Rica', 'CR', '{national_id,passport,drivers_licence}', true),
    ('Croatia', 'HR', '{national_id,passport,drivers_licence}', true),
    ('Cuba', 'CU', '{national_id,passport}', false),
    ('Cyprus', 'CY', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Czech Republic', 'CZ', '{national_id,passport,drivers_licence}', true),
    ('Denmark', 'DK', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Djibouti', 'DJ', '{national_id,passport}', false),
    ('Dominica', 'DM', '{passport,drivers_licence}', false),
    ('Dominican Republic', 'DO', '{national_id,passport,drivers_licence}', true),
    ('DR Congo', 'CD', '{national_id,passport}', false),
    ('Ecuador', 'EC', '{national_id,passport,drivers_licence}', true),
    ('Egypt', 'EG', '{national_id,passport,drivers_licence}', true),
    ('El Salvador', 'SV', '{national_id,passport,drivers_licence}', true),
    ('Equatorial Guinea', 'GQ', '{national_id,passport}', false),
    ('Eritrea', 'ER', '{national_id,passport}', false),
    ('Estonia', 'EE', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Eswatini', 'SZ', '{national_id,passport,drivers_licence}', true),
    ('Ethiopia', 'ET', '{national_id,passport,drivers_licence}', true),
    ('Fiji', 'FJ', '{passport,drivers_licence}', false),
    ('Finland', 'FI', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('France', 'FR', '{national_id,passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('Gabon', 'GA', '{national_id,passport}', false),
    ('Gambia', 'GM', '{national_id,passport}', false),
    ('Georgia', 'GE', '{national_id,passport}', false),
    ('Germany', 'DE', '{national_id,passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('Ghana', 'GH', '{national_id,passport,drivers_licence}', true),
    ('Greece', 'GR', '{national_id,passport,drivers_licence}', true),
    ('Grenada', 'GD', '{passport,drivers_licence}', false),
    ('Guatemala', 'GT', '{national_id,passport,drivers_licence}', true),
    ('Guinea', 'GN', '{national_id,passport}', false),
    ('Guinea-Bissau', 'GW', '{national_id,passport}', false),
    ('Guyana', 'GY', '{national_id,passport,drivers_licence}', true),
    ('Haiti', 'HT', '{national_id,passport}', false),
    ('Honduras', 'HN', '{national_id,passport,drivers_licence}', true),
    ('Hungary', 'HU', '{national_id,passport,drivers_licence}', true),
    ('Iceland', 'IS', '{national_id,passport,drivers_licence}', true),
    ('India', 'IN', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Indonesia', 'ID', '{national_id,passport,drivers_licence}', true),
    ('Iran', 'IR', '{national_id,passport}', false),
    ('Iraq', 'IQ', '{national_id,passport}', false),
    ('Ireland', 'IE', '{national_id,passport,drivers_licence}', true),
    ('Israel', 'IL', '{national_id,passport,drivers_licence}', true),
    ('Italy', 'IT', '{national_id,passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('Ivory Coast', 'CI', '{national_id,passport}', false),
    ('Jamaica', 'JM', '{national_id,passport,drivers_licence}', true),
    ('Japan', 'JP', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Jordan', 'JO', '{national_id,passport}', false),
    ('Kazakhstan', 'KZ', '{national_id,passport}', false),
    ('Kenya', 'KE', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Kiribati', 'KI', '{passport}', false),
    ('Kuwait', 'KW', '{national_id,passport}', false),
    ('Kyrgyzstan', 'KG', '{national_id,passport}', false),
    ('Laos', 'LA', '{national_id,passport}', false),
    ('Latvia', 'LV', '{national_id,passport,drivers_licence}', true),
    ('Lebanon', 'LB', '{national_id,passport}', false),
    ('Lesotho', 'LS', '{national_id,passport,drivers_licence}', true),
    ('Liberia', 'LR', '{national_id,passport}', false),
    ('Libya', 'LY', '{national_id,passport}', false),
    ('Liechtenstein', 'LI', '{national_id,passport}', false),
    ('Lithuania', 'LT', '{national_id,passport,drivers_licence}', true),
    ('Luxembourg', 'LU', '{national_id,passport,drivers_licence}', true),
    ('Madagascar', 'MG', '{national_id,passport}', false),
    ('Malawi', 'MW', '{national_id,passport}', false),
    ('Malaysia', 'MY', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Maldives', 'MV', '{national_id,passport}', false),
    ('Mali', 'ML', '{national_id,passport}', false),
    ('Malta', 'MT', '{national_id,passport,drivers_licence}', true),
    ('Marshall Islands', 'MH', '{passport}', false),
    ('Mauritania', 'MR', '{national_id,passport}', false),
    ('Mauritius', 'MU', '{national_id,passport,drivers_licence}', true),
    ('Mexico', 'MX', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Micronesia', 'FM', '{passport}', false),
    ('Moldova', 'MD', '{national_id,passport}', false),
    ('Monaco', 'MC', '{national_id,passport}', false),
    ('Mongolia', 'MN', '{national_id,passport}', false),
    ('Montenegro', 'ME', '{national_id,passport,drivers_licence}', true),
    ('Morocco', 'MA', '{national_id,passport,drivers_licence}', true),
    ('Mozambique', 'MZ', '{national_id,passport,drivers_licence}', true),
    ('Myanmar', 'MM', '{national_id,passport}', false),
    ('Namibia', 'NA', '{national_id,passport,drivers_licence,refugee_travel}', true),
    ('Nauru', 'NR', '{passport}', false),
    ('Nepal', 'NP', '{national_id,passport}', false),
    ('Netherlands', 'NL', '{national_id,passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('New Zealand', 'NZ', '{passport,drivers_licence,residence_permit}', true),
    ('Nicaragua', 'NI', '{national_id,passport,drivers_licence}', true),
    ('Niger', 'NE', '{national_id,passport}', false),
    ('Nigeria', 'NG', '{national_id,passport,drivers_licence,refugee_travel}', true),
    ('North Korea', 'KP', '{national_id,passport}', false),
    ('North Macedonia', 'MK', '{national_id,passport,drivers_licence}', true),
    ('Norway', 'NO', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Oman', 'OM', '{national_id,passport}', false),
    ('Pakistan', 'PK', '{national_id,passport,drivers_licence}', true),
    ('Palau', 'PW', '{passport}', false),
    ('Palestine', 'PS', '{national_id,passport}', false),
    ('Panama', 'PA', '{national_id,passport,drivers_licence}', true),
    ('Papua New Guinea', 'PG', '{passport,drivers_licence}', false),
    ('Paraguay', 'PY', '{national_id,passport,drivers_licence}', true),
    ('Peru', 'PE', '{national_id,passport,drivers_licence}', true),
    ('Philippines', 'PH', '{national_id,passport,drivers_licence}', true),
    ('Poland', 'PL', '{national_id,passport,drivers_licence}', true),
    ('Portugal', 'PT', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Qatar', 'QA', '{national_id,passport}', false),
    ('Romania', 'RO', '{national_id,passport,drivers_licence}', true),
    ('Russia', 'RU', '{national_id,passport,drivers_licence}', true),
    ('Rwanda', 'RW', '{national_id,passport}', false),
    ('Saint Kitts and Nevis', 'KN', '{passport,drivers_licence}', false),
    ('Saint Lucia', 'LC', '{passport,drivers_licence}', false),
    ('Saint Vincent', 'VC', '{passport,drivers_licence}', false),
    ('Samoa', 'WS', '{passport}', false),
    ('San Marino', 'SM', '{national_id,passport}', false),
    ('Sao Tome and Principe', 'ST', '{national_id,passport}', false),
    ('Saudi Arabia', 'SA', '{national_id,passport,residence_permit}', true),
    ('Senegal', 'SN', '{national_id,passport}', false),
    ('Serbia', 'RS', '{national_id,passport,drivers_licence}', true),
    ('Seychelles', 'SC', '{national_id,passport}', false),
    ('Sierra Leone', 'SL', '{national_id,passport}', false),
    ('Singapore', 'SG', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Slovakia', 'SK', '{national_id,passport,drivers_licence}', true),
    ('Slovenia', 'SI', '{national_id,passport,drivers_licence}', true),
    ('Solomon Islands', 'SB', '{passport}', false),
    ('Somalia', 'SO', '{national_id,passport}', false),
    ('South Africa', 'ZA', '{national_id,passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('South Korea', 'KR', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('South Sudan', 'SS', '{national_id,passport}', false),
    ('Spain', 'ES', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Sri Lanka', 'LK', '{national_id,passport,drivers_licence}', true),
    ('Sudan', 'SD', '{national_id,passport}', false),
    ('Suriname', 'SR', '{national_id,passport}', false),
    ('Sweden', 'SE', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Switzerland', 'CH', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Syria', 'SY', '{national_id,passport}', false),
    ('Taiwan', 'TW', '{national_id,passport,residence_permit}', true),
    ('Tajikistan', 'TJ', '{national_id,passport}', false),
    ('Tanzania', 'TZ', '{national_id,passport,drivers_licence}', true),
    ('Thailand', 'TH', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Timor-Leste', 'TL', '{national_id,passport}', false),
    ('Togo', 'TG', '{national_id,passport}', false),
    ('Tonga', 'TO', '{passport}', false),
    ('Trinidad and Tobago', 'TT', '{national_id,passport,drivers_licence}', true),
    ('Tunisia', 'TN', '{national_id,passport,drivers_licence}', true),
    ('Turkey', 'TR', '{national_id,passport,drivers_licence}', true),
    ('Turkmenistan', 'TM', '{national_id,passport}', false),
    ('Tuvalu', 'TV', '{passport}', false),
    ('Uganda', 'UG', '{national_id,passport}', false),
    ('Ukraine', 'UA', '{national_id,passport,drivers_licence}', true),
    ('United Arab Emirates', 'AE', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('United Kingdom', 'GB', '{passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('United States', 'US', '{passport,drivers_licence,residence_permit,refugee_travel}', true),
    ('Uruguay', 'UY', '{national_id,passport,drivers_licence}', true),
    ('Uzbekistan', 'UZ', '{national_id,passport}', false),
    ('Vanuatu', 'VU', '{passport}', false),
    ('Vatican City', 'VA', '{passport}', false),
    ('Venezuela', 'VE', '{national_id,passport,drivers_licence}', true),
    ('Vietnam', 'VN', '{national_id,passport,drivers_licence,residence_permit}', true),
    ('Yemen', 'YE', '{national_id,passport}', false),
    ('Zambia', 'ZM', '{national_id,passport,drivers_licence}', true),
    ('Zimbabwe', 'ZW', '{national_id,passport,drivers_licence}', true)
ON CONFLICT DO NOTHING;

-- 4. Profile verification columns
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verification_level integer DEFAULT 0;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verification_country text;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verification_date timestamptz;
ALTER TABLE chain_profiles ADD COLUMN IF NOT EXISTS verification_expiry timestamptz;

-- 5. Audit log for admin actions on verifications
CREATE TABLE IF NOT EXISTS chain_verification_audit_log (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id uuid REFERENCES chain_verification_requests_v2(id) ON DELETE CASCADE,
    action text NOT NULL,  -- approved, rejected, requested_info, suspended, unsuspended, reuploaded
    admin_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
    notes text,
    created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_vrfy_audit_request ON chain_verification_audit_log(request_id);

-- 6. Update existing profiles: set verified = TRUE profiles to level 2
UPDATE chain_profiles SET verification_level = 2 WHERE (verified = TRUE OR is_verified = TRUE) AND verification_level = 0;
