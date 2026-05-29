create extension if not exists pgcrypto;

create table if not exists chain_profiles (
    id uuid primary key default gen_random_uuid(),
    auth_user_id uuid,
    username text unique,
    email text,
    full_name text,
    bio text,
    gender text,
    age integer,
    country_origin text,
    current_location text,
    phone text,
    residential_address text,
    town text,
    region text,
    country_of_birth text,
    date_of_birth date,
    current_residential_location text,
    avatar_url text,
    profile_photo text,
    cover_url text,
    cover_photo text,
    creator_category text,
    profile_type text default 'member',
    interests jsonb default '[]'::jsonb,
    languages jsonb default '[]'::jsonb,
    is_public boolean default true,
    is_verified boolean default false,
    is_premium boolean default false,
    premium_tier text default 'free',
    wallet_balance numeric(12,2) default 0,
    profile_completion integer default 0,
    profile_completed boolean default false,
    onboarding_step text default 'profile_setup',
    password_set boolean default false,
    auth_provider text,
    provider_user_id text,
    last_login_at timestamptz,
    login_count integer default 0,
    linked_providers jsonb default '[]'::jsonb,
    username_slug text,
    oauth_metadata jsonb default '{}'::jsonb,
    is_creator boolean default false,
    is_online boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_live_rooms (
    id uuid primary key default gen_random_uuid(),
    host_id uuid,
    creator_id uuid,
    profile_id uuid,
    host_profile_id uuid,
    title text,
    room_title text,
    host_name text,
    welcome_message text,
    category text,
    access_type text default 'public',
    is_live boolean default false,
    status text default 'draft',
    viewer_count integer default 0,
    viewers integer default 0,
    cover_url text,
    thumbnail_url text,
    mp3_url text,
    youtube_url text,
    entry_fee numeric(12,2) default 0,
    coins_required integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_posts (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    caption text,
    content text,
    body text,
    media_url text,
    image_url text,
    video_url text,
    category text,
    likes_count integer default 0,
    comments_count integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_stories (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    caption text,
    media_url text,
    image_url text,
    video_url text,
    expires_at timestamptz,
    status text default 'active',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_notifications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    title text,
    body text,
    message text,
    type text,
    notification_type text,
    target_url text,
    link_url text,
    is_read boolean default false,
    created_at timestamptz default now()
);

create table if not exists chain_live_viewers (
    id uuid primary key default gen_random_uuid(),
    room_id uuid,
    profile_id uuid,
    display_name text,
    joined_at timestamptz default now(),
    left_at timestamptz,
    created_at timestamptz default now()
);

create table if not exists chain_gifts (
    id uuid primary key default gen_random_uuid(),
    sender_profile_id uuid,
    receiver_profile_id uuid,
    gift_name text,
    emoji text,
    gift_icon text,
    coins integer default 0,
    amount numeric(12,2) default 0,
    created_at timestamptz default now()
);

create table if not exists chain_gift_events (
    id uuid primary key default gen_random_uuid(),
    sender_profile_id uuid,
    receiver_profile_id uuid,
    gift_id uuid,
    gift_name text,
    emoji text,
    coins integer default 0,
    created_at timestamptz default now()
);

create table if not exists chain_live_gifts (
    id uuid primary key default gen_random_uuid(),
    room_id uuid,
    sender_profile_id uuid,
    host_profile_id uuid,
    display_name text,
    gift_name text,
    emoji text,
    gift_icon text,
    coins integer default 0,
    amount numeric(12,2) default 0,
    created_at timestamptz default now()
);

create table if not exists chain_wallets (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    coin_balance integer default 0,
    gift_earnings integer default 0,
    pending_withdrawal integer default 0,
    total_spent integer default 0,
    total_received integer default 0,
    status text default 'active',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_admin_users (
    id uuid primary key default gen_random_uuid(),
    username text unique not null,
    email text unique,
    full_name text,
    role text default 'admin',
    is_master boolean default false,
    is_active boolean default true,
    password_hash text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_admin_audit_log (
    id uuid primary key default gen_random_uuid(),
    admin_id uuid,
    action text,
    target_type text,
    target_id text,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

create table if not exists chain_site_settings (
    id uuid primary key default gen_random_uuid(),
    setting_key text unique not null,
    setting_value jsonb default '{}'::jsonb,
    updated_by uuid,
    updated_at timestamptz default now()
);

insert into chain_admin_users (username, role, is_master, is_active, password_hash, full_name)
select 'chainkasera', 'developer', true, true, null, 'CHAIN Master Developer'
where not exists (
    select 1 from chain_admin_users where username = 'chainkasera'
);
