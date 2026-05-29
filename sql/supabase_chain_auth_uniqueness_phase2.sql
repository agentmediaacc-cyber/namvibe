alter table if exists chain_profiles
    add column if not exists email text,
    add column if not exists phone text,
    add column if not exists normalized_email text,
    add column if not exists normalized_phone text,
    add column if not exists signup_method text,
    add column if not exists auth_provider text,
    add column if not exists terms_accepted boolean default false,
    add column if not exists human_confirmed boolean default false;

create or replace view chain_duplicate_account_report as
select 'username' as duplicate_field, lower(username) as duplicate_value, count(*) as duplicate_count
from chain_profiles
where username is not null and trim(username) <> ''
group by lower(username)
having count(*) > 1
union all
select 'normalized_email' as duplicate_field, lower(normalized_email) as duplicate_value, count(*) as duplicate_count
from chain_profiles
where normalized_email is not null and trim(normalized_email) <> ''
group by lower(normalized_email)
having count(*) > 1
union all
select 'normalized_phone' as duplicate_field, normalized_phone as duplicate_value, count(*) as duplicate_count
from chain_profiles
where normalized_phone is not null and trim(normalized_phone) <> ''
group by normalized_phone
having count(*) > 1;

do $$
begin
    if not exists (select 1 from chain_duplicate_account_report where duplicate_field = 'username') then
        execute 'create unique index if not exists idx_chain_profiles_username_lower_unique on chain_profiles ((lower(username))) where username is not null';
    else
        raise notice 'Duplicate usernames detected. Review chain_duplicate_account_report before creating username uniqueness index.';
    end if;

    if not exists (select 1 from chain_duplicate_account_report where duplicate_field = 'normalized_email') then
        execute 'create unique index if not exists idx_chain_profiles_normalized_email_lower_unique on chain_profiles ((lower(normalized_email))) where normalized_email is not null';
    else
        raise notice 'Duplicate normalized emails detected. Review chain_duplicate_account_report before creating email uniqueness index.';
    end if;

    if not exists (select 1 from chain_duplicate_account_report where duplicate_field = 'normalized_phone') then
        execute 'create unique index if not exists idx_chain_profiles_normalized_phone_unique on chain_profiles (normalized_phone) where normalized_phone is not null';
    else
        raise notice 'Duplicate normalized phones detected. Review chain_duplicate_account_report before creating phone uniqueness index.';
    end if;
end $$;

select * from chain_duplicate_account_report;
