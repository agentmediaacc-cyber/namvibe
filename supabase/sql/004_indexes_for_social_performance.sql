-- Namvibe social performance indexes.
-- Review table/column names before execution.
-- These indexes are written to support common RLS and feed filters.

CREATE INDEX IF NOT EXISTS idx_posts_author_status_published_at
  ON public.posts (author_id, status, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_posts_audience_status_published_at
  ON public.posts (audience, status, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_posts_created_at_desc
  ON public.posts (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_comments_post_created_at
  ON public.comments (post_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_likes_post_user
  ON public.likes (post_id, user_id);

CREATE INDEX IF NOT EXISTS idx_post_views_post_user
  ON public.post_views (post_id, user_id);

CREATE INDEX IF NOT EXISTS idx_post_views_post_session
  ON public.post_views (post_id, session_key);

CREATE INDEX IF NOT EXISTS idx_stories_author_expires_at
  ON public.stories (author_id, expires_at DESC);

CREATE INDEX IF NOT EXISTS idx_stories_audience_expires_at
  ON public.stories (audience, expires_at DESC);

CREATE INDEX IF NOT EXISTS idx_story_views_story_user
  ON public.story_views (story_id, user_id);

CREATE INDEX IF NOT EXISTS idx_story_views_story_session
  ON public.story_views (story_id, session_key);

CREATE INDEX IF NOT EXISTS idx_follows_following_follower
  ON public.follows (following_id, follower_id);

CREATE INDEX IF NOT EXISTS idx_friend_requests_pair_status
  ON public.friend_requests (from_user_id, to_user_id, status);

CREATE INDEX IF NOT EXISTS idx_friend_requests_to_status
  ON public.friend_requests (to_user_id, status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_recipient_read_created
  ON public.notifications (recipient_id, is_read, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created
  ON public.messages (conversation_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_messages_sender_created
  ON public.messages (sender_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_profiles_username
  ON public.profiles (username);
