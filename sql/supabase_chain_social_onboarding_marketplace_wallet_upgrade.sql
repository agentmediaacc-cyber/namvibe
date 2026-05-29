create extension if not exists pgcrypto;

alter table if exists chain_profiles
    add column if not exists zodiac_sign text,
    add column if not exists show_zodiac boolean default false,
    add column if not exists profile_visibility text default 'public',
    add column if not exists creator_mode_enabled boolean default false,
    add column if not exists seller_mode_enabled boolean default false,
    add column if not exists dating_mode_enabled boolean default false,
    add column if not exists premium_mode_enabled boolean default false,
    add column if not exists account_mode text default 'member',
    add column if not exists is_online boolean default false;

create table if not exists chain_user_preferences (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    live_categories jsonb default '[]'::jsonb,
    post_categories jsonb default '[]'::jsonb,
    language_preferences jsonb default '[]'::jsonb,
    dating_interest jsonb default '[]'::jsonb,
    creator_interest boolean default false,
    seller_interest boolean default false,
    preferred_regions jsonb default '[]'::jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_user_verifications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    consent_accepted boolean default false,
    real_person_confirmed boolean default false,
    verification_status text default 'pending',
    selfie_url text,
    admin_notes text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_profile_avatars (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    avatar_mode text default 'upload',
    avatar_url text,
    system_avatar_key text,
    is_anonymous boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

alter table if exists chain_wallets
    add column if not exists available_balance integer default 0,
    add column if not exists pending_withdrawal_balance integer default 0,
    add column if not exists wallet_pin_hash text,
    add column if not exists wallet_pin_enabled boolean default false,
    add column if not exists topup_reference_prefix text default 'CHAIN-TOPUP';

create table if not exists chain_wallet_topups (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    reference text unique not null,
    method text not null,
    amount_nad numeric(12,2) not null,
    coins_requested integer not null,
    payment_gateway text,
    proof_url text,
    status text default 'pending',
    admin_notes text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_wallet_withdrawals (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    amount_nad numeric(12,2) not null,
    coins_redeemed integer not null,
    destination_method text,
    destination_reference text,
    status text default 'pending',
    admin_notes text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_wallet_pin_resets (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    status text default 'pending',
    verification_status text default 'pending',
    id_copy_url text,
    reason text,
    admin_notes text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_marketplace_items (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    item_type text not null,
    title text not null,
    description text,
    media_url text,
    preview_url text,
    cover_url text,
    price_coins integer default 0,
    price_nad numeric(12,2) default 0,
    is_premium_locked boolean default false,
    approval_status text default 'pending',
    moderation_status text default 'pending',
    is_public boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_music_albums (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid,
    title text not null,
    description text,
    genre text,
    album_cover_url text,
    release_date date,
    price_coins integer default 0,
    approval_status text default 'pending',
    is_public boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_music_tracks (
    id uuid primary key default gen_random_uuid(),
    album_id uuid,
    profile_id uuid,
    title text not null,
    audio_url text,
    duration_seconds integer,
    price_coins integer default 0,
    price_nad numeric(12,2) default 0,
    is_premium_locked boolean default false,
    approval_status text default 'pending',
    is_public boolean default false,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_media_purchases (
    id uuid primary key default gen_random_uuid(),
    buyer_profile_id uuid,
    item_id uuid,
    item_type text,
    amount_nad numeric(12,2) default 0,
    coins_spent integer default 0,
    status text default 'completed',
    created_at timestamptz default now()
);

create table if not exists chain_dating_profiles (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    is_enabled boolean default false,
    dating_intent text,
    dating_interest jsonb default '[]'::jsonb,
    approval_status text default 'active',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_user_privacy_settings (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    profile_visibility text default 'public',
    who_can_view_profile text default 'everyone',
    allow_profile_discovery boolean default true,
    allow_contact_from text default 'everyone',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists chain_user_call_settings (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid unique,
    allow_messages boolean default true,
    allow_audio_calls boolean default true,
    allow_video_calls boolean default true,
    allow_high_quality_media boolean default true,
    allow_status_video boolean default true,
    allow_music_uploads boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists idx_chain_user_preferences_profile_id on chain_user_preferences(profile_id);
create index if not exists idx_chain_user_verifications_status on chain_user_verifications(verification_status);
create index if not exists idx_chain_wallet_topups_status on chain_wallet_topups(status);
create index if not exists idx_chain_wallet_withdrawals_status on chain_wallet_withdrawals(status);
create index if not exists idx_chain_marketplace_items_status on chain_marketplace_items(approval_status);
create index if not exists idx_chain_music_albums_status on chain_music_albums(approval_status);
create index if not exists idx_chain_music_tracks_status on chain_music_tracks(approval_status);
create index if not exists idx_chain_dating_profiles_enabled on chain_dating_profiles(is_enabled);
