create extension if not exists "pgcrypto";

create table if not exists public.chain_profile_passes (
  id uuid primary key default gen_random_uuid(),
  actor_profile_id uuid references public.chain_profiles(id) on delete cascade,
  target_profile_id uuid references public.chain_profiles(id) on delete cascade,
  created_at timestamptz default now(),
  unique(actor_profile_id, target_profile_id)
);

create table if not exists public.chain_super_likes (
  id uuid primary key default gen_random_uuid(),
  actor_profile_id uuid references public.chain_profiles(id) on delete cascade,
  target_profile_id uuid references public.chain_profiles(id) on delete cascade,
  created_at timestamptz default now(),
  unique(actor_profile_id, target_profile_id)
);

create table if not exists public.chain_matches (
  id uuid primary key default gen_random_uuid(),
  profile_one_id uuid references public.chain_profiles(id) on delete cascade,
  profile_two_id uuid references public.chain_profiles(id) on delete cascade,
  match_reason text default 'Mutual like',
  created_at timestamptz default now()
);

create table if not exists public.chain_notifications (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text not null,
  message text,
  target_url text,
  is_read boolean default false,
  created_at timestamptz default now()
);

notify pgrst, 'reload schema';
