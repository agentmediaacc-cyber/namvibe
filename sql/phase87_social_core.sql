-- Phase 87: Social Core Systems - Friend System

-- 1. Friend Requests
CREATE TABLE IF NOT EXISTS public.chain_friend_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sender_profile_id UUID NOT NULL REFERENCES public.chain_profiles(id) ON DELETE CASCADE,
    recipient_profile_id UUID NOT NULL REFERENCES public.chain_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'pending', -- 'pending', 'accepted', 'declined', 'cancelled'
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(sender_profile_id, recipient_profile_id)
);

CREATE INDEX IF NOT EXISTS idx_friend_requests_sender ON public.chain_friend_requests(sender_profile_id);
CREATE INDEX IF NOT EXISTS idx_friend_requests_recipient ON public.chain_friend_requests(recipient_profile_id);
CREATE INDEX IF NOT EXISTS idx_friend_requests_status ON public.chain_friend_requests(status);

-- 2. Friends
CREATE TABLE IF NOT EXISTS public.chain_friends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id_1 UUID NOT NULL REFERENCES public.chain_profiles(id) ON DELETE CASCADE,
    profile_id_2 UUID NOT NULL REFERENCES public.chain_profiles(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'friend', -- 'friend', 'close_friend', 'best_friend'
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CHECK (profile_id_1 < profile_id_2), -- Ensure unique pair and order
    UNIQUE(profile_id_1, profile_id_2)
);

CREATE INDEX IF NOT EXISTS idx_friends_p1 ON public.chain_friends(profile_id_1);
CREATE INDEX IF NOT EXISTS idx_friends_p2 ON public.chain_friends(profile_id_2);
CREATE INDEX IF NOT EXISTS idx_friends_status ON public.chain_friends(status);

-- 3. Profile Counters
ALTER TABLE public.chain_profiles ADD COLUMN IF NOT EXISTS friends_count INTEGER DEFAULT 0;
