ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS email text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS phone text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS normalized_email text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS normalized_phone text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS gender text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS date_of_birth date;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS zodiac_sign text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS account_mode text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS creator_category text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS relationship_status text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS languages text[];
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS interests text[];
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS profile_completed boolean default false;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS terms_accepted boolean default false;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS human_confirmed boolean default false;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS avatar_url text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS cover_url text;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS anonymous_profile boolean default false;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS allow_zodiac_display boolean default false;
ALTER TABLE IF EXISTS chain_profiles ADD COLUMN IF NOT EXISTS allow_birthday_notifications boolean default true;

CREATE TABLE IF NOT EXISTS chain_user_preferences (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    live_categories text[],
    post_categories text[],
    language_preferences text[],
    dating_interest text[],
    creator_interest boolean default false,
    seller_interest boolean default false,
    preferred_regions text[],
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_user_privacy_settings (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    profile_visibility text default 'public',
    who_can_view_profile text default 'everyone',
    allow_profile_discovery boolean default true,
    allow_contact_from text default 'everyone',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_user_call_settings (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    allow_messages boolean default true,
    allow_audio_calls boolean default true,
    allow_video_calls boolean default true,
    allow_high_quality_media boolean default true,
    allow_status_video boolean default true,
    allow_music_uploads boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_profile_avatars (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    avatar_mode text default 'upload',
    avatar_url text,
    system_avatar_key text,
    is_anonymous boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_dating_profiles (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    is_enabled boolean default false,
    dating_intent text,
    dating_interest text[],
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

CREATE TABLE IF NOT EXISTS chain_user_verifications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    consent_accepted boolean default false,
    real_person_confirmed boolean default false,
    verification_status text default 'self-attested',
    selfie_url text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);
