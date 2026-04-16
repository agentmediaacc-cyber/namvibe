create extension if not exists "pgcrypto";

create table if not exists public.posts (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    full_name text,
    username text,
    email text,
    post_type text default 'text',
    title text,
    caption text,
    hashtags text,
    tagged_users text,
    audience text default 'Public',
    share_to text default 'Main Feed',
    group_name text,
    single_user text,
    specific_user text,
    community_name text,
    background_theme text default 'theme-purple',
    font_theme text default 'font-modern',
    crop_style text default 'cover',
    image_effect text default 'none',
    video_mode text default 'normal',
    display_mode text default 'cover',
    overlay_text text,
    flyer_background text default 'gradient-violet',
    flyer_text_color text default '#ffffff',
    flyer_layout text default 'centered',
    flyer_title text,
    flyer_body text,
    flyer_cta text,
    music_track text,
    motion_effect text default 'none',
    motion_status text,
    poll_question text,
    poll_options text,
    media_type text default 'text',
    media_url text,
    allow_comments boolean default true,
    allow_share boolean default true,
    save_story boolean default false,
    premium_badge boolean default false,
    views_count integer default 0,
    likes_count integer default 0,
    comments_count integer default 0,
    shares_count integer default 0,
    forwards_count integer default 0,
    saves_count integer default 0,
    status text default 'published',
    created_at timestamptz default now()
);

alter table public.posts add column if not exists post_type text default 'text';
alter table public.posts add column if not exists hashtags text;
alter table public.posts add column if not exists tagged_users text;
alter table public.posts add column if not exists specific_user text;
alter table public.posts add column if not exists community_name text;
alter table public.posts add column if not exists display_mode text default 'cover';
alter table public.posts add column if not exists overlay_text text;
alter table public.posts add column if not exists flyer_background text default 'gradient-violet';
alter table public.posts add column if not exists flyer_text_color text default '#ffffff';
alter table public.posts add column if not exists flyer_layout text default 'centered';
alter table public.posts add column if not exists flyer_title text;
alter table public.posts add column if not exists flyer_body text;
alter table public.posts add column if not exists flyer_cta text;
alter table public.posts add column if not exists music_track text;
alter table public.posts add column if not exists motion_effect text default 'none';
alter table public.posts add column if not exists motion_status text;
alter table public.posts add column if not exists poll_question text;
alter table public.posts add column if not exists poll_options text;
alter table public.posts add column if not exists views_count integer default 0;
alter table public.posts add column if not exists likes_count integer default 0;
alter table public.posts add column if not exists comments_count integer default 0;
alter table public.posts add column if not exists shares_count integer default 0;
alter table public.posts add column if not exists forwards_count integer default 0;
alter table public.posts add column if not exists saves_count integer default 0;

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
