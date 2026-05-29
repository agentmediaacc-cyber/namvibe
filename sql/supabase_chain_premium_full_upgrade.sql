create extension if not exists "pgcrypto";

create table if not exists public.chain_profiles (
  id uuid primary key default gen_random_uuid()
);

alter table public.chain_profiles
  add column if not exists auth_user_id text,
  add column if not exists username text,
  add column if not exists email text,
  add column if not exists full_name text,
  add column if not exists bio text,
  add column if not exists gender text,
  add column if not exists age int,
  add column if not exists country_origin text,
  add column if not exists current_location text,
  add column if not exists phone text,
  add column if not exists avatar_url text,
  add column if not exists cover_url text,
  add column if not exists profile_video_url text,
  add column if not exists interests text[],
  add column if not exists languages text[],
  add column if not exists relationship_status text,
  add column if not exists creator_category text,
  add column if not exists is_public boolean default true,
  add column if not exists is_verified boolean default false,
  add column if not exists is_premium boolean default false,
  add column if not exists premium_tier text default 'free',
  add column if not exists followers_count int default 0,
  add column if not exists following_count int default 0,
  add column if not exists profile_views int default 0,
  add column if not exists total_likes int default 0,
  add column if not exists wallet_balance numeric default 0,
  add column if not exists created_at timestamptz default now(),
  add column if not exists updated_at timestamptz default now();

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'chain_profiles_username_key') then
    alter table public.chain_profiles add constraint chain_profiles_username_key unique (username);
  end if;
end $$;

create table if not exists public.chain_posts (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  body text,
  caption text,
  media_url text,
  category text,
  status text default 'published',
  visibility text default 'public',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chain_stories (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  media_url text,
  caption text,
  status text default 'active',
  created_at timestamptz default now(),
  expires_at timestamptz default (now() + interval '24 hours')
);

create table if not exists public.chain_live_rooms (
  id uuid primary key default gen_random_uuid(),
  host_profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text,
  category text,
  description text,
  host_name text,
  welcome_message text,
  youtube_url text,
  youtube_embed_url text,
  mp3_url text,
  access_type text default 'public',
  entry_fee numeric default 0,
  status text default 'live',
  is_live boolean default true,
  viewer_count int default 0,
  gift_total numeric default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now(),
  ended_at timestamptz
);

create table if not exists public.chain_live_comments (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete set null,
  display_name text,
  body text,
  comment text,
  status text default 'visible',
  created_at timestamptz default now()
);

create table if not exists public.chain_live_gifts (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  sender_profile_id uuid references public.chain_profiles(id) on delete set null,
  host_profile_id uuid references public.chain_profiles(id) on delete set null,
  display_name text,
  gift_name text,
  gift_icon text,
  emoji text,
  amount numeric default 0,
  coins int default 0,
  status text default 'sent',
  created_at timestamptz default now()
);

create table if not exists public.chain_live_viewers (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete set null,
  display_name text,
  status text default 'watching',
  joined_at timestamptz default now(),
  left_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists public.chain_live_cohost_requests (
  id uuid primary key default gen_random_uuid(),
  room_id uuid references public.chain_live_rooms(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete set null,
  display_name text,
  status text default 'pending',
  created_at timestamptz default now()
);

create table if not exists public.chain_notifications (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text,
  body text,
  message text,
  type text,
  notification_type text default 'general',
  target_url text,
  is_read boolean default false,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists public.chain_wallets (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid unique references public.chain_profiles(id) on delete cascade,
  coin_balance numeric default 0,
  gift_earnings numeric default 0,
  pending_withdrawal numeric default 0,
  total_spent numeric default 0,
  total_received numeric default 0,
  status text default 'active',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chain_wallet_transactions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  related_profile_id uuid references public.chain_profiles(id) on delete set null,
  transaction_type text,
  coins numeric default 0,
  description text,
  status text default 'completed',
  created_at timestamptz default now()
);

create table if not exists public.chain_profile_actions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  label text,
  href text,
  icon text,
  kind text default 'link',
  is_active boolean default true,
  created_at timestamptz default now()
);

create table if not exists public.chain_followers (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  follower_profile_id uuid references public.chain_profiles(id) on delete cascade,
  following_profile_id uuid references public.chain_profiles(id) on delete cascade,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists public.chain_profile_likes (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  liker_key text,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists public.chain_favorites (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  target_profile_id uuid references public.chain_profiles(id) on delete cascade,
  target_post_id uuid references public.chain_posts(id) on delete cascade,
  target_room_id uuid references public.chain_live_rooms(id) on delete cascade,
  status text default 'active',
  created_at timestamptz default now()
);

create table if not exists public.chain_recent_views (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete set null,
  viewer_profile_id uuid references public.chain_profiles(id) on delete set null,
  viewed_profile_id uuid references public.chain_profiles(id) on delete cascade,
  viewed_post_id uuid references public.chain_posts(id) on delete cascade,
  viewed_room_id uuid references public.chain_live_rooms(id) on delete cascade,
  view_type text,
  created_at timestamptz default now()
);

create table if not exists public.chain_chat_threads (
  id uuid primary key default gen_random_uuid(),
  profile_one_id uuid references public.chain_profiles(id) on delete cascade,
  profile_two_id uuid references public.chain_profiles(id) on delete cascade,
  title text,
  last_message text,
  status text default 'active',
  created_at timestamptz default now(),
  last_message_at timestamptz default now()
);

create table if not exists public.chain_chat_messages (
  id uuid primary key default gen_random_uuid(),
  thread_id uuid references public.chain_chat_threads(id) on delete cascade,
  conversation_id uuid,
  sender_profile_id uuid references public.chain_profiles(id) on delete cascade,
  receiver_profile_id uuid references public.chain_profiles(id) on delete cascade,
  message text,
  message_type text default 'text',
  status text default 'sent',
  created_at timestamptz default now()
);

create table if not exists public.chain_video_calls (
  id uuid primary key default gen_random_uuid(),
  caller_profile_id uuid references public.chain_profiles(id) on delete cascade,
  receiver_profile_id uuid references public.chain_profiles(id) on delete cascade,
  call_type text default 'video',
  status text default 'started',
  created_at timestamptz default now(),
  ended_at timestamptz
);

create table if not exists public.chain_premium_subscriptions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  premium_tier text default 'free',
  status text default 'inactive',
  started_at timestamptz default now(),
  expires_at timestamptz
);

create table if not exists public.chain_creator_tools (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid unique references public.chain_profiles(id) on delete cascade,
  creator_notes text,
  featured_links text[],
  studio_enabled boolean default false,
  status text default 'active',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chain_reports (
  id uuid primary key default gen_random_uuid(),
  reporter_profile_id uuid references public.chain_profiles(id) on delete set null,
  reported_profile_id uuid references public.chain_profiles(id) on delete cascade,
  reason text,
  status text default 'open',
  created_at timestamptz default now()
);

create table if not exists public.chain_blocks (
  id uuid primary key default gen_random_uuid(),
  blocker_profile_id uuid references public.chain_profiles(id) on delete cascade,
  blocked_profile_id uuid references public.chain_profiles(id) on delete cascade,
  status text default 'active',
  created_at timestamptz default now()
);

create index if not exists idx_chain_profiles_username on public.chain_profiles(username);
create index if not exists idx_chain_profiles_auth_user_id on public.chain_profiles(auth_user_id);
create index if not exists idx_chain_profiles_created_at on public.chain_profiles(created_at desc);
create index if not exists idx_chain_posts_profile_id on public.chain_posts(profile_id);
create index if not exists idx_chain_posts_created_at on public.chain_posts(created_at desc);
create index if not exists idx_chain_posts_category on public.chain_posts(category);
create index if not exists idx_chain_posts_status on public.chain_posts(status);
create index if not exists idx_chain_stories_profile_id on public.chain_stories(profile_id);
create index if not exists idx_chain_stories_created_at on public.chain_stories(created_at desc);
create index if not exists idx_chain_live_rooms_profile_id on public.chain_live_rooms(host_profile_id);
create index if not exists idx_chain_live_rooms_created_at on public.chain_live_rooms(created_at desc);
create index if not exists idx_chain_live_rooms_status on public.chain_live_rooms(status);
create index if not exists idx_chain_live_rooms_category on public.chain_live_rooms(category);
create index if not exists idx_chain_live_comments_room_id on public.chain_live_comments(room_id);
create index if not exists idx_chain_live_gifts_room_id on public.chain_live_gifts(room_id);
create index if not exists idx_chain_live_viewers_room_id on public.chain_live_viewers(room_id);
create index if not exists idx_chain_live_viewers_status on public.chain_live_viewers(status);
create index if not exists idx_chain_live_cohost_requests_room_id on public.chain_live_cohost_requests(room_id);
create index if not exists idx_chain_notifications_profile_id on public.chain_notifications(profile_id);
create index if not exists idx_chain_notifications_status on public.chain_notifications(status);
create index if not exists idx_chain_wallets_profile_id on public.chain_wallets(profile_id);
create index if not exists idx_chain_wallet_transactions_profile_id on public.chain_wallet_transactions(profile_id);
create index if not exists idx_chain_profile_actions_profile_id on public.chain_profile_actions(profile_id);
create index if not exists idx_chain_followers_profile_id on public.chain_followers(profile_id);
create index if not exists idx_chain_followers_following_profile_id on public.chain_followers(following_profile_id);
create index if not exists idx_chain_profile_likes_profile_id on public.chain_profile_likes(profile_id);
create index if not exists idx_chain_favorites_profile_id on public.chain_favorites(profile_id);
create index if not exists idx_chain_recent_views_profile_id on public.chain_recent_views(profile_id);
create index if not exists idx_chain_recent_views_viewed_profile_id on public.chain_recent_views(viewed_profile_id);
create index if not exists idx_chain_chat_threads_created_at on public.chain_chat_threads(created_at desc);
create index if not exists idx_chain_chat_messages_thread_id on public.chain_chat_messages(thread_id);
create index if not exists idx_chain_chat_messages_created_at on public.chain_chat_messages(created_at desc);
create index if not exists idx_chain_video_calls_created_at on public.chain_video_calls(created_at desc);
create index if not exists idx_chain_premium_subscriptions_profile_id on public.chain_premium_subscriptions(profile_id);
create index if not exists idx_chain_reports_status on public.chain_reports(status);
create index if not exists idx_chain_blocks_blocker_profile_id on public.chain_blocks(blocker_profile_id);

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

drop policy if exists "public read profiles" on public.chain_profiles;
create policy "public read profiles" on public.chain_profiles for select using (is_public = true or auth.role() = 'authenticated');
drop policy if exists "auth manage profiles" on public.chain_profiles;
create policy "auth manage profiles" on public.chain_profiles for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "public read posts" on public.chain_posts;
create policy "public read posts" on public.chain_posts for select using (visibility = 'public' or auth.role() = 'authenticated');
drop policy if exists "auth manage posts" on public.chain_posts;
create policy "auth manage posts" on public.chain_posts for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "public read stories" on public.chain_stories;
create policy "public read stories" on public.chain_stories for select using (true);
drop policy if exists "auth manage stories" on public.chain_stories;
create policy "auth manage stories" on public.chain_stories for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "public read live rooms" on public.chain_live_rooms;
create policy "public read live rooms" on public.chain_live_rooms for select using (access_type = 'public' or auth.role() = 'authenticated');
drop policy if exists "auth manage live rooms" on public.chain_live_rooms;
create policy "auth manage live rooms" on public.chain_live_rooms for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "public read live activity" on public.chain_live_comments;
create policy "public read live activity" on public.chain_live_comments for select using (true);
drop policy if exists "public read live gifts" on public.chain_live_gifts;
create policy "public read live gifts" on public.chain_live_gifts for select using (true);
drop policy if exists "public read live viewers" on public.chain_live_viewers;
create policy "public read live viewers" on public.chain_live_viewers for select using (true);
drop policy if exists "public read cohost requests" on public.chain_live_cohost_requests;
create policy "public read cohost requests" on public.chain_live_cohost_requests for select using (auth.role() = 'authenticated');

drop policy if exists "auth manage live comments" on public.chain_live_comments;
create policy "auth manage live comments" on public.chain_live_comments for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth manage live gifts" on public.chain_live_gifts;
create policy "auth manage live gifts" on public.chain_live_gifts for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth manage live viewers" on public.chain_live_viewers;
create policy "auth manage live viewers" on public.chain_live_viewers for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth manage cohost requests" on public.chain_live_cohost_requests;
create policy "auth manage cohost requests" on public.chain_live_cohost_requests for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "auth notifications" on public.chain_notifications;
create policy "auth notifications" on public.chain_notifications for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth wallets" on public.chain_wallets;
create policy "auth wallets" on public.chain_wallets for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth wallet transactions" on public.chain_wallet_transactions;
create policy "auth wallet transactions" on public.chain_wallet_transactions for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "public read profile actions" on public.chain_profile_actions;
create policy "public read profile actions" on public.chain_profile_actions for select using (is_active = true or auth.role() = 'authenticated');
drop policy if exists "auth manage profile actions" on public.chain_profile_actions;
create policy "auth manage profile actions" on public.chain_profile_actions for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "auth social actions" on public.chain_followers;
create policy "auth social actions" on public.chain_followers for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth likes" on public.chain_profile_likes;
create policy "auth likes" on public.chain_profile_likes for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth favorites" on public.chain_favorites;
create policy "auth favorites" on public.chain_favorites for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth recent views" on public.chain_recent_views;
create policy "auth recent views" on public.chain_recent_views for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

drop policy if exists "auth chat threads" on public.chain_chat_threads;
create policy "auth chat threads" on public.chain_chat_threads for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth chat messages" on public.chain_chat_messages;
create policy "auth chat messages" on public.chain_chat_messages for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth video calls" on public.chain_video_calls;
create policy "auth video calls" on public.chain_video_calls for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth premium subscriptions" on public.chain_premium_subscriptions;
create policy "auth premium subscriptions" on public.chain_premium_subscriptions for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth creator tools" on public.chain_creator_tools;
create policy "auth creator tools" on public.chain_creator_tools for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth reports" on public.chain_reports;
create policy "auth reports" on public.chain_reports for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');
drop policy if exists "auth blocks" on public.chain_blocks;
create policy "auth blocks" on public.chain_blocks for all using (auth.role() = 'authenticated') with check (auth.role() = 'authenticated');

notify pgrst, 'reload schema';
