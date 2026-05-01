-- Namvibe social policy foundation.
-- Assumptions:
-- - user-owned rows use a UUID-like owner column such as user_id / author_id / recipient_id.
-- - public content uses audience='public' and published/active flags.
-- - friend-locked content depends on an accepted friendship row.
-- Review every policy before execution.

DO $$
BEGIN
  IF to_regclass('public.profiles') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='profiles' AND policyname='profiles_public_read') THEN
    EXECUTE $policy$
      CREATE POLICY profiles_public_read ON public.profiles
      FOR SELECT
      USING (coalesce(is_private, false) = false OR id = auth.uid() OR user_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.profiles') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='profiles' AND policyname='profiles_owner_write') THEN
    EXECUTE $policy$
      CREATE POLICY profiles_owner_write ON public.profiles
      FOR ALL
      USING (id = auth.uid() OR user_id = auth.uid())
      WITH CHECK (id = auth.uid() OR user_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.posts') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='posts' AND policyname='posts_read_visible') THEN
    EXECUTE $policy$
      CREATE POLICY posts_read_visible ON public.posts
      FOR SELECT
      USING (
        author_id = auth.uid()
        OR (
          status = 'published'
          AND (
            audience = 'public'
            OR (
              audience = 'followers'
              AND EXISTS (
                SELECT 1 FROM public.follows f
                WHERE f.following_id = posts.author_id
                  AND f.follower_id = auth.uid()
              )
            )
            OR (
              audience = 'friends'
              AND EXISTS (
                SELECT 1 FROM public.friend_requests fr
                WHERE fr.status = 'accepted'
                  AND (
                    (fr.from_user_id = posts.author_id AND fr.to_user_id = auth.uid())
                    OR
                    (fr.to_user_id = posts.author_id AND fr.from_user_id = auth.uid())
                  )
              )
            )
          )
        )
      );
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.posts') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='posts' AND policyname='posts_owner_write') THEN
    EXECUTE $policy$
      CREATE POLICY posts_owner_write ON public.posts
      FOR ALL
      USING (author_id = auth.uid())
      WITH CHECK (author_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.comments') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='comments' AND policyname='comments_owner_insert_read_visible') THEN
    EXECUTE $policy$
      CREATE POLICY comments_owner_insert_read_visible ON public.comments
      FOR SELECT
      USING (
        author_id = auth.uid()
        OR EXISTS (
          SELECT 1 FROM public.posts p
          WHERE p.id = comments.post_id
            AND (
              p.author_id = auth.uid()
              OR (p.status = 'published' AND p.audience = 'public')
            )
        )
      );
    $policy$;
    EXECUTE $policy$
      CREATE POLICY comments_owner_write ON public.comments
      FOR ALL
      USING (author_id = auth.uid())
      WITH CHECK (author_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.likes') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='likes' AND policyname='likes_owner_write') THEN
    EXECUTE $policy$
      CREATE POLICY likes_owner_write ON public.likes
      FOR ALL
      USING (user_id = auth.uid())
      WITH CHECK (user_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.stories') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='stories' AND policyname='stories_read_visible') THEN
    EXECUTE $policy$
      CREATE POLICY stories_read_visible ON public.stories
      FOR SELECT
      USING (
        author_id = auth.uid()
        OR (
          expires_at > now()
          AND (
            audience = 'public'
            OR (
              audience = 'followers'
              AND EXISTS (
                SELECT 1 FROM public.follows f
                WHERE f.following_id = stories.author_id
                  AND f.follower_id = auth.uid()
              )
            )
            OR (
              audience = 'friends'
              AND EXISTS (
                SELECT 1 FROM public.friend_requests fr
                WHERE fr.status = 'accepted'
                  AND (
                    (fr.from_user_id = stories.author_id AND fr.to_user_id = auth.uid())
                    OR
                    (fr.to_user_id = stories.author_id AND fr.from_user_id = auth.uid())
                  )
              )
            )
          )
        )
      );
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.stories') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='stories' AND policyname='stories_owner_write') THEN
    EXECUTE $policy$
      CREATE POLICY stories_owner_write ON public.stories
      FOR ALL
      USING (author_id = auth.uid())
      WITH CHECK (author_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.notifications') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='notifications' AND policyname='notifications_owner_access') THEN
    EXECUTE $policy$
      CREATE POLICY notifications_owner_access ON public.notifications
      FOR ALL
      USING (recipient_id = auth.uid())
      WITH CHECK (recipient_id = auth.uid());
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.conversations') IS NOT NULL
     AND to_regclass('public.conversation_participants') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='conversations' AND policyname='conversations_participant_read') THEN
    EXECUTE $policy$
      CREATE POLICY conversations_participant_read ON public.conversations
      FOR SELECT
      USING (
        EXISTS (
          SELECT 1 FROM public.conversation_participants cp
          WHERE cp.conversation_id = conversations.id
            AND cp.user_id = auth.uid()
        )
      );
    $policy$;
    EXECUTE $policy$
      CREATE POLICY conversations_participant_write ON public.conversations
      FOR UPDATE
      USING (
        EXISTS (
          SELECT 1 FROM public.conversation_participants cp
          WHERE cp.conversation_id = conversations.id
            AND cp.user_id = auth.uid()
        )
      );
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF to_regclass('public.messages') IS NOT NULL
     AND to_regclass('public.conversation_participants') IS NOT NULL
     AND NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='public' AND tablename='messages' AND policyname='messages_participant_access') THEN
    EXECUTE $policy$
      CREATE POLICY messages_participant_access ON public.messages
      FOR SELECT
      USING (
        EXISTS (
          SELECT 1 FROM public.conversation_participants cp
          WHERE cp.conversation_id = messages.conversation_id
            AND cp.user_id = auth.uid()
        )
      );
    $policy$;
    EXECUTE $policy$
      CREATE POLICY messages_sender_insert ON public.messages
      FOR INSERT
      WITH CHECK (
        sender_id = auth.uid()
        AND EXISTS (
          SELECT 1 FROM public.conversation_participants cp
          WHERE cp.conversation_id = messages.conversation_id
            AND cp.user_id = auth.uid()
        )
      );
    $policy$;
  END IF;
END $$;
