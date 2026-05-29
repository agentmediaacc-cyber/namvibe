begin;

create extension if not exists "pgcrypto";

drop table if exists public.chain_blocks;
drop table if exists public.chain_reports;
drop table if exists public.chain_creator_tools;
drop table if exists public.chain_premium_subscriptions;
drop table if exists public.chain_video_calls;
drop table if exists public.chain_chat_messages;
drop table if exists public.chain_chat_threads;
drop table if exists public.chain_recent_views;
drop table if exists public.chain_favorites;
drop table if exists public.chain_profile_likes;
drop table if exists public.chain_followers;
drop table if exists public.chain_profile_actions;
drop table if exists public.chain_wallet_transactions;
drop table if exists public.chain_wallets;
drop table if exists public.chain_notifications;
drop table if exists public.chain_live_cohost_requests;
drop table if exists public.chain_live_viewers;
drop table if exists public.chain_live_gifts;
drop table if exists public.chain_live_comments;
drop table if exists public.chain_live_rooms;
drop table if exists public.chain_stories;
drop table if exists public.chain_posts;
drop table if exists public.chain_profiles;

create table public.chain_profiles (
    id uuid primary key default gen_random_uuid(),
    auth_user_id text unique,
    username text not null unique,
    email text,
    full_name text not null,
    bio text default '',
    gender text,
    age integer,
    country_origin text,
    current_location text,
    phone text,
    avatar_url text,
    cover_url text,
    profile_video_url text,
    interests text[] default '{}'::text[],
    languages text[] default '{}'::text[],
    relationship_status text,
    creator_category text,
    profile_type text default 'member',
    is_public boolean default true,
    is_verified boolean default false,
    is_premium boolean default false,
    premium_tier text default 'free',
    followers_count integer default 0,
    following_count integer default 0,
    profile_views integer default 0,
    total_likes integer default 0,
    wallet_balance numeric(12,2) default 0,
    profile_completion integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_posts (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    body text,
    caption text,
    category text,
    media_url text,
    visibility text default 'public',
    status text default 'published',
    likes_count integer default 0,
    comments_count integer default 0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_stories (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    caption text,
    media_url text,
    category text,
    status text default 'active',
    expires_at timestamptz,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_live_rooms (
    id uuid primary key default gen_random_uuid(),
    host_profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    title text not null,
    host_name text,
    category text,
    access_type text default 'public',
    entry_fee numeric(12,2) default 0,
    youtube_url text,
    youtube_embed_url text,
    mp3_url text,
    mp3_name text,
    cover_url text,
    welcome_message text,
    status text default 'live',
    viewer_count integer default 0,
    gift_total numeric(12,2) default 0,
    comments_enabled boolean default true,
    gifts_enabled boolean default true,
    is_public boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_live_comments (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.chain_live_rooms(id) on delete cascade,
    profile_id uuid references public.chain_profiles(id) on delete set null,
    display_name text,
    body text not null,
    status text default 'visible',
    created_at timestamptz default now()
);

create table public.chain_live_gifts (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.chain_live_rooms(id) on delete cascade,
    sender_profile_id uuid references public.chain_profiles(id) on delete set null,
    host_profile_id uuid references public.chain_profiles(id) on delete set null,
    display_name text,
    gift_name text,
    gift_icon text,
    amount numeric(12,2) default 0,
    status text default 'sent',
    created_at timestamptz default now()
);

create table public.chain_live_viewers (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.chain_live_rooms(id) on delete cascade,
    profile_id uuid references public.chain_profiles(id) on delete set null,
    display_name text,
    status text default 'watching',
    joined_at timestamptz default now(),
    last_seen_at timestamptz default now()
);

create table public.chain_live_cohost_requests (
    id uuid primary key default gen_random_uuid(),
    room_id uuid not null references public.chain_live_rooms(id) on delete cascade,
    profile_id uuid references public.chain_profiles(id) on delete set null,
    display_name text,
    status text default 'pending',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_notifications (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    actor_profile_id uuid references public.chain_profiles(id) on delete set null,
    title text not null,
    body text default '',
    type text default 'general',
    target_url text,
    is_read boolean default false,
    status text default 'active',
    created_at timestamptz default now()
);

create table public.chain_wallets (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null unique references public.chain_profiles(id) on delete cascade,
    coin_balance numeric(12,2) default 0,
    gift_earnings numeric(12,2) default 0,
    pending_withdrawal numeric(12,2) default 0,
    status text default 'active',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_wallet_transactions (
    id uuid primary key default gen_random_uuid(),
    wallet_id uuid references public.chain_wallets(id) on delete cascade,
    profile_id uuid references public.chain_profiles(id) on delete cascade,
    transaction_type text not null,
    description text,
    coins numeric(12,2) default 0,
    amount numeric(12,2) default 0,
    status text default 'completed',
    created_at timestamptz default now()
);

create table public.chain_profile_actions (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    label text not null,
    href text not null,
    icon text,
    kind text default 'link',
    sort_order integer default 0,
    status text default 'active',
    created_at timestamptz default now()
);

create table public.chain_followers (
    id uuid primary key default gen_random_uuid(),
    follower_profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    following_profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    created_at timestamptz default now(),
    unique (follower_profile_id, following_profile_id)
);

create table public.chain_profile_likes (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    liker_profile_id uuid references public.chain_profiles(id) on delete set null,
    liker_key text,
    created_at timestamptz default now(),
    unique (profile_id, liker_key)
);

create table public.chain_favorites (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid references public.chain_profiles(id) on delete cascade,
    target_profile_id uuid references public.chain_profiles(id) on delete cascade,
    target_post_id uuid references public.chain_posts(id) on delete cascade,
    target_room_id uuid references public.chain_live_rooms(id) on delete cascade,
    created_at timestamptz default now()
);

create table public.chain_recent_views (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid references public.chain_profiles(id) on delete cascade,
    viewer_profile_id uuid references public.chain_profiles(id) on delete set null,
    viewed_profile_id uuid references public.chain_profiles(id) on delete cascade,
    viewed_post_id uuid references public.chain_posts(id) on delete cascade,
    viewed_room_id uuid references public.chain_live_rooms(id) on delete cascade,
    view_type text default 'profile',
    created_at timestamptz default now()
);

create table public.chain_chat_threads (
    id uuid primary key default gen_random_uuid(),
    profile_one_id uuid not null references public.chain_profiles(id) on delete cascade,
    profile_two_id uuid not null references public.chain_profiles(id) on delete cascade,
    title text,
    status text default 'active',
    last_message text,
    last_message_at timestamptz default now(),
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_chat_messages (
    id uuid primary key default gen_random_uuid(),
    thread_id uuid not null references public.chain_chat_threads(id) on delete cascade,
    sender_profile_id uuid references public.chain_profiles(id) on delete set null,
    receiver_profile_id uuid references public.chain_profiles(id) on delete set null,
    body text not null,
    message text,
    message_type text default 'text',
    status text default 'sent',
    created_at timestamptz default now()
);

create table public.chain_video_calls (
    id uuid primary key default gen_random_uuid(),
    caller_profile_id uuid references public.chain_profiles(id) on delete set null,
    receiver_profile_id uuid references public.chain_profiles(id) on delete set null,
    call_type text default 'video',
    status text default 'started',
    started_at timestamptz default now(),
    ended_at timestamptz,
    created_at timestamptz default now()
);

create table public.chain_premium_subscriptions (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    tier text default 'free',
    status text default 'active',
    starts_at timestamptz default now(),
    ends_at timestamptz,
    created_at timestamptz default now()
);

create table public.chain_creator_tools (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid not null unique references public.chain_profiles(id) on delete cascade,
    studio_enabled boolean default false,
    monetization_enabled boolean default false,
    creator_notes text default '',
    featured_links jsonb default '[]'::jsonb,
    status text default 'active',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table public.chain_reports (
    id uuid primary key default gen_random_uuid(),
    reporter_profile_id uuid references public.chain_profiles(id) on delete set null,
    target_profile_id uuid references public.chain_profiles(id) on delete cascade,
    reason text,
    details text,
    status text default 'open',
    created_at timestamptz default now()
);

create table public.chain_blocks (
    id uuid primary key default gen_random_uuid(),
    blocker_profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    blocked_profile_id uuid not null references public.chain_profiles(id) on delete cascade,
    created_at timestamptz default now(),
    unique (blocker_profile_id, blocked_profile_id)
);

create index chain_profiles_username_idx on public.chain_profiles (username);
create index chain_profiles_auth_user_id_idx on public.chain_profiles (auth_user_id);
create index chain_profiles_created_at_idx on public.chain_profiles (created_at desc);

create index chain_posts_profile_id_idx on public.chain_posts (profile_id);
create index chain_posts_category_idx on public.chain_posts (category);
create index chain_posts_created_at_idx on public.chain_posts (created_at desc);

create index chain_stories_profile_id_idx on public.chain_stories (profile_id);
create index chain_stories_created_at_idx on public.chain_stories (created_at desc);

create index chain_live_rooms_host_profile_id_idx on public.chain_live_rooms (host_profile_id);
create index chain_live_rooms_category_idx on public.chain_live_rooms (category);
create index chain_live_rooms_status_idx on public.chain_live_rooms (status);
create index chain_live_rooms_created_at_idx on public.chain_live_rooms (created_at desc);

create index chain_live_comments_room_id_idx on public.chain_live_comments (room_id);
create index chain_live_comments_created_at_idx on public.chain_live_comments (created_at desc);

create index chain_live_gifts_room_id_idx on public.chain_live_gifts (room_id);
create index chain_live_gifts_host_profile_id_idx on public.chain_live_gifts (host_profile_id);
create index chain_live_gifts_created_at_idx on public.chain_live_gifts (created_at desc);

create index chain_live_viewers_room_id_idx on public.chain_live_viewers (room_id);
create index chain_live_viewers_profile_id_idx on public.chain_live_viewers (profile_id);

create index chain_live_cohost_requests_room_id_idx on public.chain_live_cohost_requests (room_id);
create index chain_live_cohost_requests_status_idx on public.chain_live_cohost_requests (status);

create index chain_notifications_profile_id_idx on public.chain_notifications (profile_id);
create index chain_notifications_status_idx on public.chain_notifications (status);
create index chain_notifications_created_at_idx on public.chain_notifications (created_at desc);

create index chain_wallet_transactions_profile_id_idx on public.chain_wallet_transactions (profile_id);
create index chain_wallet_transactions_created_at_idx on public.chain_wallet_transactions (created_at desc);

create index chain_profile_actions_profile_id_idx on public.chain_profile_actions (profile_id);
create index chain_profile_actions_status_idx on public.chain_profile_actions (status);

create index chain_followers_follower_idx on public.chain_followers (follower_profile_id);
create index chain_followers_following_idx on public.chain_followers (following_profile_id);

create index chain_profile_likes_profile_id_idx on public.chain_profile_likes (profile_id);
create index chain_profile_likes_created_at_idx on public.chain_profile_likes (created_at desc);

create index chain_favorites_profile_id_idx on public.chain_favorites (profile_id);
create index chain_recent_views_profile_id_idx on public.chain_recent_views (profile_id);
create index chain_recent_views_viewed_profile_id_idx on public.chain_recent_views (viewed_profile_id);
create index chain_recent_views_created_at_idx on public.chain_recent_views (created_at desc);

create index chain_chat_threads_profile_one_id_idx on public.chain_chat_threads (profile_one_id);
create index chain_chat_threads_profile_two_id_idx on public.chain_chat_threads (profile_two_id);
create index chain_chat_threads_last_message_at_idx on public.chain_chat_threads (last_message_at desc);

create index chain_chat_messages_thread_id_idx on public.chain_chat_messages (thread_id);
create index chain_chat_messages_created_at_idx on public.chain_chat_messages (created_at desc);

create index chain_video_calls_caller_profile_id_idx on public.chain_video_calls (caller_profile_id);
create index chain_video_calls_receiver_profile_id_idx on public.chain_video_calls (receiver_profile_id);
create index chain_video_calls_status_idx on public.chain_video_calls (status);

create index chain_premium_subscriptions_profile_id_idx on public.chain_premium_subscriptions (profile_id);
create index chain_premium_subscriptions_status_idx on public.chain_premium_subscriptions (status);

create index chain_reports_target_profile_id_idx on public.chain_reports (target_profile_id);
create index chain_reports_status_idx on public.chain_reports (status);

alter table public.chain_profiles enable row level security;
alter table public.chain_posts enable row level security;
alter table public.chain_stories enable row level security;
alter table public.chain_live_rooms enable row level security;
alter table public.chain_live_comments enable row level security;
alter table public.chain_live_gifts enable row level security;
alter table public.chain_live_viewers enable row level security;
alter table public.chain_live_cohost_requests enable row level security;
alter table public.chain_notifications enable row level security;
alter table public.chain_wallets enable row level security;
alter table public.chain_wallet_transactions enable row level security;
alter table public.chain_profile_actions enable row level security;
alter table public.chain_followers enable row level security;
alter table public.chain_profile_likes enable row level security;
alter table public.chain_favorites enable row level security;
alter table public.chain_recent_views enable row level security;
alter table public.chain_chat_threads enable row level security;
alter table public.chain_chat_messages enable row level security;
alter table public.chain_video_calls enable row level security;
alter table public.chain_premium_subscriptions enable row level security;
alter table public.chain_creator_tools enable row level security;
alter table public.chain_reports enable row level security;
alter table public.chain_blocks enable row level security;

create policy "dev_public_read_profiles" on public.chain_profiles for select using (is_public = true or auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_profiles" on public.chain_profiles for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_posts" on public.chain_posts for select using (visibility = 'public' or auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_posts" on public.chain_posts for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_stories" on public.chain_stories for select using (status = 'active' or auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_stories" on public.chain_stories for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_live_rooms" on public.chain_live_rooms for select using (is_public = true or auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_live_rooms" on public.chain_live_rooms for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_live_comments" on public.chain_live_comments for select using (true);
create policy "dev_auth_manage_live_comments" on public.chain_live_comments for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_live_gifts" on public.chain_live_gifts for select using (true);
create policy "dev_auth_manage_live_gifts" on public.chain_live_gifts for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_live_viewers" on public.chain_live_viewers for select using (true);
create policy "dev_auth_manage_live_viewers" on public.chain_live_viewers for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_public_read_live_cohost_requests" on public.chain_live_cohost_requests for select using (true);
create policy "dev_auth_manage_live_cohost_requests" on public.chain_live_cohost_requests for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

create policy "dev_auth_manage_notifications" on public.chain_notifications for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_wallets" on public.chain_wallets for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_wallet_transactions" on public.chain_wallet_transactions for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_profile_actions" on public.chain_profile_actions for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_followers" on public.chain_followers for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_profile_likes" on public.chain_profile_likes for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_favorites" on public.chain_favorites for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_recent_views" on public.chain_recent_views for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_chat_threads" on public.chain_chat_threads for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_chat_messages" on public.chain_chat_messages for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_video_calls" on public.chain_video_calls for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_premium_subscriptions" on public.chain_premium_subscriptions for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_creator_tools" on public.chain_creator_tools for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_reports" on public.chain_reports for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));
create policy "dev_auth_manage_blocks" on public.chain_blocks for all using (auth.role() in ('authenticated', 'service_role')) with check (auth.role() in ('authenticated', 'service_role'));

select pg_notify('pgrst', 'reload schema');

commit;
