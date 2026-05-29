create extension if not exists "pgcrypto";

create table if not exists public.chain_chat_conversations (
  id uuid primary key default gen_random_uuid(),
  profile_one_id uuid references public.chain_profiles(id) on delete cascade,
  profile_two_id uuid references public.chain_profiles(id) on delete cascade,
  title text,
  last_message text,
  last_message_at timestamptz,
  created_at timestamptz default now()
);

create table if not exists public.chain_chat_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid references public.chain_chat_conversations(id) on delete cascade,
  sender_profile_id uuid references public.chain_profiles(id) on delete cascade,
  receiver_profile_id uuid references public.chain_profiles(id) on delete cascade,
  message text not null,
  message_type text default 'text',
  is_read boolean default false,
  created_at timestamptz default now()
);

create table if not exists public.chain_chat_reactions (
  id uuid primary key default gen_random_uuid(),
  message_id uuid references public.chain_chat_messages(id) on delete cascade,
  profile_id uuid references public.chain_profiles(id) on delete cascade,
  reaction text not null,
  created_at timestamptz default now()
);

notify pgrst, 'reload schema';
