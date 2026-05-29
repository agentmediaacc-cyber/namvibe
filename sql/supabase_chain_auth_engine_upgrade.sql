begin;

alter table if exists public.chain_profiles
    add column if not exists auth_provider text,
    add column if not exists provider_user_id text,
    add column if not exists last_login_at timestamptz,
    add column if not exists login_count integer default 0,
    add column if not exists profile_completed boolean default false,
    add column if not exists username_slug text,
    add column if not exists avatar_url text,
    add column if not exists oauth_metadata jsonb default '{}'::jsonb;

create unique index if not exists chain_profiles_auth_user_id_unique_idx
    on public.chain_profiles (auth_user_id)
    where auth_user_id is not null;

create index if not exists chain_profiles_email_idx on public.chain_profiles (email);
create index if not exists chain_profiles_username_idx on public.chain_profiles (username);
create index if not exists chain_profiles_provider_user_id_idx on public.chain_profiles (provider_user_id);
create index if not exists chain_profiles_last_login_at_idx on public.chain_profiles (last_login_at desc);

create table if not exists public.chain_login_events (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid references public.chain_profiles(id) on delete set null,
    auth_user_id text,
    provider text,
    email text,
    ip_address text,
    user_agent text,
    status text,
    created_at timestamptz default now()
);

create index if not exists chain_login_events_profile_id_idx on public.chain_login_events (profile_id);
create index if not exists chain_login_events_auth_user_id_idx on public.chain_login_events (auth_user_id);
create index if not exists chain_login_events_provider_idx on public.chain_login_events (provider);
create index if not exists chain_login_events_created_at_idx on public.chain_login_events (created_at desc);

alter table if exists public.chain_login_events enable row level security;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public'
          and tablename = 'chain_login_events'
          and policyname = 'dev_auth_manage_login_events'
    ) then
        create policy "dev_auth_manage_login_events"
            on public.chain_login_events
            for all
            using (auth.role() in ('authenticated', 'service_role'))
            with check (auth.role() in ('authenticated', 'service_role'));
    end if;
end $$;

commit;
