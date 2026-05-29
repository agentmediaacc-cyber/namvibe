create extension if not exists "pgcrypto";

create table if not exists public.chain_wallets (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid unique references public.chain_profiles(id) on delete cascade,
  coin_balance int default 0,
  gift_earnings int default 0,
  pending_withdrawal int default 0,
  total_spent int default 0,
  total_received int default 0,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists public.chain_gift_catalog (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  emoji text default '🎁',
  coin_price int not null default 1,
  is_active boolean default true,
  created_at timestamptz default now()
);

create table if not exists public.chain_wallet_transactions (
  id uuid primary key default gen_random_uuid(),
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  transaction_type text not null,
  coins int not null default 0,
  description text,
  related_profile_id uuid references public.chain_profiles(id) on delete set null,
  created_at timestamptz default now()
);

create table if not exists public.chain_gift_events (
  id uuid primary key default gen_random_uuid(),
  sender_profile_id uuid references public.chain_profiles(id) on delete set null,
  receiver_profile_id uuid references public.chain_profiles(id) on delete cascade,
  gift_id uuid references public.chain_gift_catalog(id) on delete set null,
  gift_name text,
  emoji text,
  coins int default 0,
  created_at timestamptz default now()
);

insert into public.chain_gift_catalog (name, emoji, coin_price)
select * from (
  values
  ('Rose', '🌹', 5),
  ('Heart', '💖', 10),
  ('Crown', '👑', 25),
  ('Diamond', '💎', 50),
  ('Luxury Car', '🏎️', 100),
  ('VIP Star', '⭐', 150)
) as gifts(name, emoji, coin_price)
where not exists (select 1 from public.chain_gift_catalog);

notify pgrst, 'reload schema';
