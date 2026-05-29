create extension if not exists "pgcrypto";

create table if not exists public.chain_profile_views (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  viewer_key text,
  created_at timestamptz default now()
);

create table if not exists public.chain_profile_likes (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  liker_key text,
  created_at timestamptz default now()
);

create table if not exists public.chain_followers (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  follower_key text,
  created_at timestamptz default now()
);

create table if not exists public.chain_conversations (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text,
  created_at timestamptz default now()
);

create table if not exists public.chain_gift_events (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  gift_name text default 'Starter Gift',
  coins int default 1,
  created_at timestamptz default now()
);

create table if not exists public.chain_live_rooms (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text,
  is_live boolean default true,
  created_at timestamptz default now()
);

alter table public.chain_profile_views enable row level security;
alter table public.chain_profile_likes enable row level security;
alter table public.chain_followers enable row level security;
alter table public.chain_conversations enable row level security;
alter table public.chain_gift_events enable row level security;
alter table public.chain_live_rooms enable row level security;

drop policy if exists "public read profile views" on public.chain_profile_views;
create policy "public read profile views" on public.chain_profile_views for select using (true);

drop policy if exists "public read profile likes" on public.chain_profile_likes;
create policy "public read profile likes" on public.chain_profile_likes for select using (true);

drop policy if exists "public read followers" on public.chain_followers;
create policy "public read followers" on public.chain_followers for select using (true);

drop policy if exists "public read conversations" on public.chain_conversations;
create policy "public read conversations" on public.chain_conversations for select using (true);

drop policy if exists "public read gifts" on public.chain_gift_events;
create policy "public read gifts" on public.chain_gift_events for select using (true);

drop policy if exists "public read live rooms" on public.chain_live_rooms;
create policy "public read live rooms" on public.chain_live_rooms for select using (true);

notify pgrst, 'reload schema';
