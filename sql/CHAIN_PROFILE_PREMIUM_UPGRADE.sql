-- CHAIN PROFILE PREMIUM UPGRADE
-- Adds missing columns for premium profile system

ALTER TABLE public.chain_profiles 
ADD COLUMN IF NOT EXISTS profile_type text DEFAULT 'member',
ADD COLUMN IF NOT EXISTS cover_url text,
ADD COLUMN IF NOT EXISTS profile_completion int DEFAULT 0;

-- Ensure avatar_url exists (renaming profile_photo if needed, or just adding)
DO $$ 
BEGIN 
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='chain_profiles' AND column_name='avatar_url') THEN
    ALTER TABLE public.chain_profiles ADD COLUMN avatar_url text;
  END IF;
END $$;

-- Table for Posts
CREATE TABLE IF NOT EXISTS public.chain_posts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid REFERENCES public.chain_profiles(id) ON DELETE CASCADE,
  body text,
  media_url text,
  visibility text DEFAULT 'public',
  created_at timestamptz DEFAULT now()
);

-- Table for Stories
CREATE TABLE IF NOT EXISTS public.chain_stories (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_id uuid REFERENCES public.chain_profiles(id) ON DELETE CASCADE,
  media_url text,
  caption text,
  expires_at timestamptz DEFAULT (now() + interval '24 hours'),
  created_at timestamptz DEFAULT now()
);

-- Indexing for performance
CREATE INDEX IF NOT EXISTS idx_posts_profile ON public.chain_posts(profile_id);
CREATE INDEX IF NOT EXISTS idx_stories_profile ON public.chain_stories(profile_id);

-- Policies for RLS
ALTER TABLE public.chain_posts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chain_stories ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "public can read public posts" ON public.chain_posts;
CREATE POLICY "public can read public posts" ON public.chain_posts FOR SELECT USING (visibility = 'public');

DROP POLICY IF EXISTS "users can manage their own posts" ON public.chain_posts;
CREATE POLICY "users can manage their own posts" ON public.chain_posts FOR ALL USING (
  profile_id IN (SELECT id FROM public.chain_profiles WHERE auth_user_id = auth.uid())
);

DROP POLICY IF EXISTS "public can read stories" ON public.chain_stories;
CREATE POLICY "public can read stories" ON public.chain_stories FOR SELECT USING (expires_at > now());

DROP POLICY IF EXISTS "users can manage their own stories" ON public.chain_stories;
CREATE POLICY "users can manage their own stories" ON public.chain_stories FOR ALL USING (
  profile_id IN (SELECT id FROM public.chain_profiles WHERE auth_user_id = auth.uid())
);

NOTIFY pgrst, 'reload schema';
