create extension if not exists "pgcrypto";

create table if not exists public.profiles (
    id uuid primary key,
    email text unique not null,
    username text unique not null,
    full_name text not null,
    phone text unique not null,
    created_at timestamptz default now()
);

alter table public.profiles enable row level security;

drop policy if exists "profiles_select_all" on public.profiles;
create policy "profiles_select_all"
on public.profiles
for select
using (true);

drop policy if exists "profiles_insert_service_role" on public.profiles;
create policy "profiles_insert_service_role"
on public.profiles
for insert
with check (auth.role() = 'service_role');

drop policy if exists "profiles_update_owner_or_service_role" on public.profiles;
create policy "profiles_update_owner_or_service_role"
on public.profiles
for update
using (auth.uid() = id or auth.role() = 'service_role')
with check (auth.uid() = id or auth.role() = 'service_role');
