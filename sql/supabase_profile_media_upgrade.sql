alter table public.chain_profiles
add column if not exists profile_photo text,
add column if not exists cover_photo text,
add column if not exists video_intro_url text,
add column if not exists voice_intro_url text,
add column if not exists mood_status text,
add column if not exists headline text,
add column if not exists profile_completion int default 35,
add column if not exists last_active_at timestamptz default now();

notify pgrst, 'reload schema';
