-- Namvibe storage policy foundation for Supabase Storage.
-- Assumptions:
-- - buckets are named avatars, covers, posts, stories, reels, live.
-- - object names are user-scoped, for example:
--   avatars/<auth.uid()>/file.jpg
--   posts/<auth.uid()>/2026/05/file.mp4
-- Review bucket names and folder structure before execution.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename = 'objects'
      AND policyname = 'public_read_social_media'
  ) THEN
    EXECUTE $policy$
      CREATE POLICY public_read_social_media ON storage.objects
      FOR SELECT
      USING (
        bucket_id IN ('avatars', 'covers', 'posts', 'stories', 'reels', 'live')
      );
    $policy$;
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'storage'
      AND tablename = 'objects'
      AND policyname = 'owner_write_social_media'
  ) THEN
    EXECUTE $policy$
      CREATE POLICY owner_write_social_media ON storage.objects
      FOR INSERT
      WITH CHECK (
        bucket_id IN ('avatars', 'covers', 'posts', 'stories', 'reels', 'live')
        AND auth.uid()::text = (storage.foldername(name))[1]
      );
    $policy$;
    EXECUTE $policy$
      CREATE POLICY owner_update_delete_social_media ON storage.objects
      FOR UPDATE
      USING (
        bucket_id IN ('avatars', 'covers', 'posts', 'stories', 'reels', 'live')
        AND auth.uid()::text = (storage.foldername(name))[1]
      )
      WITH CHECK (
        bucket_id IN ('avatars', 'covers', 'posts', 'stories', 'reels', 'live')
        AND auth.uid()::text = (storage.foldername(name))[1]
      );
    $policy$;
    EXECUTE $policy$
      CREATE POLICY owner_delete_social_media ON storage.objects
      FOR DELETE
      USING (
        bucket_id IN ('avatars', 'covers', 'posts', 'stories', 'reels', 'live')
        AND auth.uid()::text = (storage.foldername(name))[1]
      );
    $policy$;
  END IF;
END $$;

-- Optional hardening after validation:
-- - keep avatars/covers public-read only if your product requires public profile media
-- - split private buckets from public buckets
-- - add separate policies for premium/private live uploads
