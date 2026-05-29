create extension if not exists "pgcrypto";

create table if not exists public.chain_live_rooms (
  id uuid primary key default gen_random_uuid(),
  host_profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text not null,
  welcome_message text,
  youtube_url text,
  youtube_embed_url text,
  mp3_url text,
  access_type text default 'public',
  is_live boolean default true,
  comments_enabled boolean default true,
  viewer_count int default 0,
  total_gift_coins int default 0,
  created_at timestamptz default now(),
  ended_at timestamptz
);

create table if not exists public.chain_live_viewers (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  joined_at timestamptz default now(),
  left_at timestamptz,
  unique(room_id, profile_id)
);

create table if not exists public.chain_live_comments (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  parent_comment_id uuid references public.chain_live_comments(id) on delete cascade,
  comment text not null,
  created_at timestamptz default now()
);

create table if not exists public.chain_live_blocks (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  blocked_profile_id uuid references public.chain_profiles(id) on delete cascade,
  created_at timestamptz default now(),
  unique(room_id, blocked_profile_id)
);

create table if not exists public.chain_live_gifts (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  sender_profile_id uuid references public.chain_profiles(id) on delete set null,
  host_profile_id uuid references public.chain_profiles(id) on delete cascade,
  gift_name text,
  emoji text,
  coins int default 0,
  created_at timestamptz default now()
);

create table if not exists public.chain_follows (
  id uuid primary key default gen_random_uuid(),
  follower_profile_id uuid references public.chain_profiles(id) on delete cascade,
  following_profile_id uuid references public.chain_profiles(id) on delete cascade,
  created_at timestamptz default now(),
  unique(follower_profile_id, following_profile_id)
);

notify pgrst, 'reload schema';
