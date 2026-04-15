create extension if not exists "pgcrypto";

create table if not exists public.live_rooms (
    id uuid primary key default gen_random_uuid(),
    host_user_id uuid not null,
    host_full_name text,
    host_username text,
    host_email text,
    title text not null,
    description text,
    audience text default 'Public',
    room_access text default 'Open Room',
    status text default 'offline',
    theme text default 'theme-purple',
    quality text default '1280x720',
    frame_rate integer default 30,
    view_mode text default 'normal',
    allow_gifts boolean default true,
    allow_comments boolean default true,
    allow_cohost boolean default false,
    allow_premium_join boolean default false,
    allow_premium_view boolean default false,
    vip_badge boolean default false,
    private_line boolean default false,
    location_text text,
    started_at timestamptz,
    ended_at timestamptz,
    created_at timestamptz default now()
);

create table if not exists public.live_comments (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.live_rooms(id) on delete cascade,
    user_id uuid,
    full_name text,
    username text,
    message text not null,
    is_host boolean default false,
    created_at timestamptz default now()
);

create table if not exists public.live_gifts (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.live_rooms(id) on delete cascade,
    sender_user_id uuid,
    sender_username text,
    gift_name text not null,
    token_amount integer default 0,
    created_at timestamptz default now()
);

alter table public.live_rooms enable row level security;
alter table public.live_comments enable row level security;
alter table public.live_gifts enable row level security;

drop policy if exists "live_rooms_select_all" on public.live_rooms;
create policy "live_rooms_select_all"
on public.live_rooms
for select
using (true);

drop policy if exists "live_rooms_insert_service_role" on public.live_rooms;
create policy "live_rooms_insert_service_role"
on public.live_rooms
for insert
with check (auth.role() = 'service_role');

drop policy if exists "live_rooms_update_service_role" on public.live_rooms;
create policy "live_rooms_update_service_role"
on public.live_rooms
for update
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');

drop policy if exists "live_comments_select_all" on public.live_comments;
create policy "live_comments_select_all"
on public.live_comments
for select
using (true);

drop policy if exists "live_comments_insert_service_role" on public.live_comments;
create policy "live_comments_insert_service_role"
on public.live_comments
for insert
with check (auth.role() = 'service_role');

drop policy if exists "live_gifts_select_all" on public.live_gifts;
create policy "live_gifts_select_all"
on public.live_gifts
for select
using (true);

drop policy if exists "live_gifts_insert_service_role" on public.live_gifts;
create policy "live_gifts_insert_service_role"
on public.live_gifts
for insert
with check (auth.role() = 'service_role');
