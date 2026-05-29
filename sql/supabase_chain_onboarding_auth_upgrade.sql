begin;

alter table if exists public.chain_profiles
    add column if not exists phone text,
    add column if not exists residential_address text,
    add column if not exists town text,
    add column if not exists region text,
    add column if not exists country_of_birth text,
    add column if not exists date_of_birth date,
    add column if not exists current_residential_location text,
    add column if not exists profile_completed boolean default false,
    add column if not exists onboarding_step text default 'profile_setup',
    add column if not exists password_set boolean default false,
    add column if not exists auth_provider text,
    add column if not exists linked_providers text[] default '{}'::text[],
    add column if not exists last_login_at timestamptz,
    add column if not exists login_count integer default 0;

create index if not exists chain_profiles_email_idx on public.chain_profiles (email);
create index if not exists chain_profiles_auth_user_id_idx on public.chain_profiles (auth_user_id);
create index if not exists chain_profiles_username_idx on public.chain_profiles (username);
create index if not exists chain_profiles_phone_idx on public.chain_profiles (phone);
create index if not exists chain_profiles_town_idx on public.chain_profiles (town);
create index if not exists chain_profiles_region_idx on public.chain_profiles (region);
create index if not exists chain_profiles_profile_completed_idx on public.chain_profiles (profile_completed);

create table if not exists public.chain_user_settings (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid references public.chain_profiles(id) on delete cascade,
    allow_messages boolean default true,
    allow_video_calls boolean default true,
    show_online_status boolean default true,
    profile_visibility text default 'public',
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists public.chain_account_security (
    id uuid primary key default gen_random_uuid(),
    profile_id uuid references public.chain_profiles(id) on delete cascade,
    email text,
    password_set boolean default false,
    last_password_change timestamptz,
    recovery_enabled boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists chain_user_settings_profile_id_idx on public.chain_user_settings (profile_id);
create index if not exists chain_account_security_profile_id_idx on public.chain_account_security (profile_id);
create index if not exists chain_account_security_email_idx on public.chain_account_security (email);

alter table if exists public.chain_user_settings enable row level security;
alter table if exists public.chain_account_security enable row level security;

do $$
begin
    if not exists (
        select 1 from pg_policies
        where schemaname = 'public' and tablename = 'chain_user_settings' and policyname = 'dev_auth_manage_user_settings'
    ) then
        create policy "dev_auth_manage_user_settings"
        on public.chain_user_settings
        for all
        using (auth.role() in ('authenticated', 'service_role'))
        with check (auth.role() in ('authenticated', 'service_role'));
    end if;

    if not exists (
        select 1 from pg_policies
        where schemaname = 'public' and tablename = 'chain_account_security' and policyname = 'dev_auth_manage_account_security'
    ) then
        create policy "dev_auth_manage_account_security"
        on public.chain_account_security
        for all
        using (auth.role() in ('authenticated', 'service_role'))
        with check (auth.role() in ('authenticated', 'service_role'));
    end if;
end $$;

commit;
