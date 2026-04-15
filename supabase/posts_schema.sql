create extension if not exists "pgcrypto";

create table if not exists public.posts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    full_name text,
    username text,
    email text,
    title text,
    caption text,
    audience text default 'Public',
    share_to text default 'Main Feed',
    group_name text,
    single_user text,
    background_theme text default 'theme-purple',
    font_theme text default 'font-modern',
    crop_style text default 'cover',
    image_effect text default 'none',
    video_mode text default 'normal',
    media_type text default 'text',
    media_url text,
    allow_comments boolean default true,
    allow_share boolean default true,
    save_story boolean default false,
    premium_badge boolean default false,
    status text default 'published',
    created_at timestamptz default now()
);

alter table public.posts enable row level security;

drop policy if exists "posts_select_all" on public.posts;
create policy "posts_select_all"
on public.posts
for select
using (true);

drop policy if exists "posts_insert_service_role" on public.posts;
create policy "posts_insert_service_role"
on public.posts
for insert
with check (auth.role() = 'service_role');

drop policy if exists "posts_update_service_role" on public.posts;
create policy "posts_update_service_role"
on public.posts
for update
using (auth.role() = 'service_role')
with check (auth.role() = 'service_role');
