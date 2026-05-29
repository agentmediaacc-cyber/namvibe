create extension if not exists "uuid-ossp";

create table if not exists public.chain_live_rooms (
  id uuid primary key default uuid_generate_v4(),
  title text default 'My Chain Live Room',
  host_name text default 'tjandja kasera',
  welcome_message text default 'Thank you for joining my live channel ❤️',
  youtube_url text,
  youtube_video_id text,
  youtube_embed_url text,
  mp3_url text,
  access_type text default 'public',
  entry_fee numeric default 0,
  comments_enabled boolean default true,
  gifts_enabled boolean default true,
  cohost_enabled boolean default true,
  status text default 'live',
  viewer_count int default 0,
  gift_total numeric default 0,
  created_at timestamptz default now(),
  ended_at timestamptz
);

create table if not exists public.chain_live_viewers (
  id uuid primary key default uuid_generate_v4(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  display_name text default 'Guest',
  joined_at timestamptz default now(),
  left_at timestamptz
);

create table if not exists public.chain_live_comments (
  id uuid primary key default uuid_generate_v4(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  display_name text default 'Guest',
  body text not null,
  created_at timestamptz default now()
);

create table if not exists public.chain_live_gifts (
  id uuid primary key default uuid_generate_v4(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  display_name text default 'Guest',
  gift_icon text default '🎁',
  gift_name text default 'Gift',
  amount numeric default 0,
  created_at timestamptz default now()
);

alter table public.chain_live_rooms enable row level security;
alter table public.chain_live_viewers enable row level security;
alter table public.chain_live_comments enable row level security;
alter table public.chain_live_gifts enable row level security;

drop policy if exists "chain live rooms readable" on public.chain_live_rooms;
create policy "chain live rooms readable" on public.chain_live_rooms for select using (true);

drop policy if exists "chain live viewers readable" on public.chain_live_viewers;
create policy "chain live viewers readable" on public.chain_live_viewers for select using (true);

drop policy if exists "chain live comments readable" on public.chain_live_comments;
create policy "chain live comments readable" on public.chain_live_comments for select using (true);

drop policy if exists "chain live gifts readable" on public.chain_live_gifts;
create policy "chain live gifts readable" on public.chain_live_gifts for select using (true);

notify pgrst, 'reload schema';
