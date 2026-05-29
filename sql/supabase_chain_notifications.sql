create extension if not exists "pgcrypto";

create table if not exists public.chain_notifications (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  title text not null,
  message text,
  notification_type text default 'general',
  target_url text,
  is_read boolean default false,
  created_at timestamptz default now()
);

alter table public.chain_notifications
add column if not exists notification_type text default 'general',
add column if not exists target_url text,
add column if not exists is_read boolean default false;

notify pgrst, 'reload schema';
