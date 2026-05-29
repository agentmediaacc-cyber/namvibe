create extension if not exists "pgcrypto";

create table if not exists public.chain_profiles (
  id uuid primary key default gen_random_uuid(),
  auth_user_id uuid unique,
  username text unique not null,
  email text unique,
  full_name text not null,
  age int,
  gender text,
  country_origin text,
  current_location text,
  phone text,
  bio text,
  relationship_goal text,
  languages text[],
  interests text[],
  profile_photo text,
  cover_photo text,
  video_intro_url text,
  voice_intro_url text,
  is_verified boolean default false,
  is_creator boolean default false,
  is_public boolean default true,
  online_status text default 'offline',
  profile_views int default 0,
  followers_count int default 0,
  likes_count int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chain_profile_actions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  action_type text not null,
  target_url text not null,
  label text not null,
  icon text,
  is_active boolean default true,
  sort_order int default 0,
  created_at timestamptz default now()
);

alter table public.chain_profiles enable row level security;
alter table public.chain_profile_actions enable row level security;

drop policy if exists "public can read public chain profiles" on public.chain_profiles;
create policy "public can read public chain profiles"
on public.chain_profiles for select
using (is_public = true);

drop policy if exists "public can read profile actions" on public.chain_profile_actions;
create policy "public can read profile actions"
on public.chain_profile_actions for select
using (is_active = true);
