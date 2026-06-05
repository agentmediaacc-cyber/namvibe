-- CHAIN Phase 6: Real Social Features
-- Idempotent engagement tables and counters for likes, comments, follows, saves, and notifications.

create extension if not exists "pgcrypto";

create table if not exists public.chain_follows (
  id uuid primary key default gen_random_uuid(),
  follower_profile_id uuid references public.chain_profiles(id) on delete cascade,
  following_profile_id uuid references public.chain_profiles(id) on delete cascade,
  created_at timestamptz default now(),
  unique(follower_profile_id, following_profile_id)
);

create table if not exists public.chain_post_reactions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  post_id uuid references public.chain_posts(id) on delete cascade,
  reaction_type text default 'like',
  created_at timestamptz default now(),
  unique(profile_id, post_id, reaction_type)
);

create table if not exists public.chain_post_comments (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  post_id uuid references public.chain_posts(id) on delete cascade,
  body text not null,
  created_at timestamptz default now()
);

create table if not exists public.chain_reel_reactions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  reel_id uuid references public.chain_reels(id) on delete cascade,
  reaction_type text default 'like',
  created_at timestamptz default now(),
  unique(profile_id, reel_id, reaction_type)
);

create table if not exists public.chain_reel_comments (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  reel_id uuid references public.chain_reels(id) on delete cascade,
  body text not null,
  created_at timestamptz default now()
);

create table if not exists public.chain_story_reactions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  story_id uuid references public.chain_status_posts(id) on delete cascade,
  reaction_type text default 'like',
  created_at timestamptz default now(),
  unique(profile_id, story_id, reaction_type)
);

create table if not exists public.chain_live_reactions (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  reaction_type text default 'like',
  created_at timestamptz default now()
);

create unique index if not exists idx_chain_live_reactions_unique_like
on public.chain_live_reactions(room_id, profile_id, reaction_type);

create table if not exists public.chain_saved_items (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  item_type text not null,
  item_id uuid not null,
  created_at timestamptz default now(),
  unique(profile_id, item_type, item_id)
);

create table if not exists public.chain_notification_events (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  actor_profile_id uuid references public.chain_profiles(id) on delete set null,
  event_type text not null,
  title text,
  body text,
  target_url text,
  is_read boolean default false,
  created_at timestamptz default now()
);

alter table public.chain_posts add column if not exists likes_count integer default 0;
alter table public.chain_posts add column if not exists comments_count integer default 0;
alter table public.chain_reels add column if not exists likes_count integer default 0;
alter table public.chain_reels add column if not exists comments_count integer default 0;
alter table public.chain_status_posts add column if not exists likes_count integer default 0;
alter table public.chain_live_rooms add column if not exists likes_count integer default 0;
alter table public.chain_live_rooms add column if not exists comments_count integer default 0;
alter table public.chain_profiles add column if not exists followers_count integer default 0;
alter table public.chain_profiles add column if not exists following_count integer default 0;

create index if not exists idx_chain_follows_follower on public.chain_follows(follower_profile_id);
create index if not exists idx_chain_follows_following on public.chain_follows(following_profile_id);
create index if not exists idx_chain_post_reactions_post on public.chain_post_reactions(post_id);
create index if not exists idx_chain_post_comments_post on public.chain_post_comments(post_id, created_at desc);
create index if not exists idx_chain_reel_reactions_reel on public.chain_reel_reactions(reel_id);
create index if not exists idx_chain_reel_comments_reel on public.chain_reel_comments(reel_id, created_at desc);
create index if not exists idx_chain_story_reactions_story on public.chain_story_reactions(story_id);
create index if not exists idx_chain_live_reactions_room on public.chain_live_reactions(room_id);
create index if not exists idx_chain_saved_items_profile on public.chain_saved_items(profile_id, created_at desc);
create index if not exists idx_chain_notification_events_profile on public.chain_notification_events(profile_id, is_read, created_at desc);

notify pgrst, 'reload schema';
