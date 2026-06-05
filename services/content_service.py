import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from html import escape
from urllib.parse import urlparse

from werkzeug.utils import secure_filename

from engines.cache_engine import cache_key, delete_cache
from services.neon_service import fast_query, write_query, get_table_columns
from services.logging_service import log_error, log_info, log_warning


IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "gif"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_MIME_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/mov"}
VISIBILITIES = {"public", "followers", "private"}

UPLOAD_FOLDERS = {
    "post": "static/uploads/posts",
    "profile_post": "static/uploads/posts",
    "reel": "static/uploads/reels",
    "story": "static/uploads/stories",
}

MAX_IMAGE_MB = 12
MAX_VIDEO_MB = 150
HASHTAG_RE = re.compile(r"(?<!\w)#([A-Za-z0-9_]{1,48})")

_LOCAL_STORE = {"posts": [], "reels": [], "stories": [], "hashtags": {}, "media": []}

CONTENT_TABLES = [
    "chain_posts",
    "chain_media_uploads",
    "chain_status_posts",
    "chain_hashtags",
    "chain_content_hashtags",
    "chain_reels",
    "chain_post_reactions",
    "chain_reel_reactions",
    "chain_story_reactions",
    "chain_post_comments",
    "chain_reel_comments",
    "chain_saved_items",
    "chain_follows",
    "chain_notifications",
    "chain_notification_events",
    "chain_conversations",
    "chain_conversation_members",
    "chain_messages",
]


def utcnow():
    return datetime.now(timezone.utc)


def is_production_env():
    return os.getenv("FLASK_ENV") == "production" or os.getenv("ENV") == "production"


def local_fallback_allowed():
    return not is_production_env()


def _persistence_mode():
    return "neon" if is_production_env() else "local_fallback_allowed"


def sanitize_text(value, max_len=2200):
    text = " ".join((value or "").replace("\x00", "").strip().split())
    if not text:
        return ""
    return escape(text[:max_len], quote=False)


def normalize_visibility(value):
    value = (value or "public").strip().lower()
    return value if value in VISIBILITIES else "public"


def parse_hashtags(*values):
    tags = []
    for value in values:
        for match in HASHTAG_RE.findall(value or ""):
            tag = match.lower()
            if tag not in tags:
                tags.append(tag)
    return tags


def hashtag_links(text):
    clean = sanitize_text(text)
    return HASHTAG_RE.sub(lambda m: f'<a href="/search?q=%23{m.group(1).lower()}">#{m.group(1)}</a>', clean)


def _extension(filename):
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].lower()


def _file_size(file_obj):
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(0)
    return size


def validate_media(file_obj, media_kind=None):
    if not file_obj or not getattr(file_obj, "filename", ""):
        return False, "No media file selected.", None
    ext = _extension(file_obj.filename)
    content_type = (getattr(file_obj, "content_type", "") or "").lower()
    is_image = ext in IMAGE_EXTENSIONS and (not content_type or content_type in IMAGE_MIME_TYPES)
    is_video = ext in VIDEO_EXTENSIONS and (not content_type or content_type in VIDEO_MIME_TYPES)
    if media_kind == "image" and not is_image:
        return False, "Only jpg, jpeg, png, webp, and gif images are allowed.", None
    if media_kind == "video" and not is_video:
        return False, "Only mp4, webm, and mov videos are allowed.", None
    if not media_kind and not (is_image or is_video):
        return False, "Only supported image or video files are allowed.", None

    size = _file_size(file_obj)
    limit_mb = MAX_VIDEO_MB if is_video else MAX_IMAGE_MB
    if size > limit_mb * 1024 * 1024:
        return False, f"File is too large. Maximum size is {limit_mb}MB.", None
    return True, None, {"kind": "video" if is_video else "image", "ext": ext, "size": size, "content_type": content_type}


def save_media_file(file_obj, upload_type, media_kind=None, profile_id=None):
    valid, error, info = validate_media(file_obj, media_kind=media_kind)
    if not valid:
        return None, error
    folder = UPLOAD_FOLDERS.get(upload_type, UPLOAD_FOLDERS["post"])
    os.makedirs(folder, exist_ok=True)
    original = secure_filename(file_obj.filename or "upload")
    filename = f"{int(time.time())}_{uuid.uuid4().hex[:10]}_{original}"
    path = os.path.join(folder, filename)
    file_obj.save(path)
    url = "/" + path.replace(os.sep, "/")
    media = {
        "id": str(uuid.uuid4()),
        "profile_id": profile_id,
        "upload_type": upload_type,
        "media_type": info["kind"],
        "file_path": path,
        "public_url": url,
        "storage_bucket": "local",
        "storage_path": path,
        "mime_type": info["content_type"],
        "file_size": info["size"],
        "original_filename": original,
        "created_at": utcnow().isoformat(),
    }
    inserted = _insert_media_metadata(media)
    if not inserted and is_production_env():
        log_error("content_media_metadata_persistence_failed", upload_type=upload_type)
        return None, "Media metadata could not be saved. Please try again."
    if not inserted:
        log_warning("content_using_local_fallback", content_type="media", profile_id=profile_id)
        _LOCAL_STORE["media"].append(media)
    return media, None


def validate_link(value):
    link = sanitize_text(value, max_len=500)
    if not link:
        return ""
    parsed = urlparse(link)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return link


def ensure_content_schema():
    if os.getenv("CHAIN_FAST_LOCAL") == "1" and not is_production_env():
        log_info("content_schema_bootstrap_skipped", reason="fast_local", persistence_mode=_persistence_mode())
        return {"ok": False, "skipped": True, "reason": "fast_local", "tables": []}
    sql = """
    CREATE EXTENSION IF NOT EXISTS pgcrypto;
    CREATE TABLE IF NOT EXISTS chain_posts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        body text,
        caption text,
        post_type text DEFAULT 'text',
        media_url text,
        video_url text,
        link_url text,
        town_tag text,
        visibility text DEFAULT 'public',
        likes_count integer DEFAULT 0,
        comments_count integer DEFAULT 0,
        shares_count integer DEFAULT 0,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now(),
        deleted_at timestamptz
    );
    CREATE TABLE IF NOT EXISTS chain_media_uploads (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
        upload_type text,
        media_type text,
        file_path text,
        public_url text,
        storage_bucket text,
        storage_path text,
        mime_type text,
        file_size bigint,
        original_filename text,
        created_at timestamptz DEFAULT now()
    );
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS post_type text DEFAULT 'text';
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS media_url text;
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS video_url text;
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS link_url text;
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS town_tag text;
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS shares_count integer DEFAULT 0;
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();
    ALTER TABLE chain_posts ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS media_type text;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS file_path text;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS public_url text;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS storage_bucket text;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS storage_path text;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS mime_type text;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS file_size bigint;
    ALTER TABLE chain_media_uploads ADD COLUMN IF NOT EXISTS original_filename text;
    CREATE TABLE IF NOT EXISTS chain_status_posts (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        status_type text DEFAULT 'story',
        caption text,
        media_url text,
        video_url text,
        visibility text DEFAULT 'public',
        expires_at timestamptz DEFAULT now() + interval '24 hours',
        likes_count integer DEFAULT 0,
        created_at timestamptz DEFAULT now(),
        deleted_at timestamptz
    );
    ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS video_url text;
    ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS likes_count integer DEFAULT 0;
    ALTER TABLE chain_status_posts ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
    CREATE TABLE IF NOT EXISTS chain_hashtags (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        tag text UNIQUE NOT NULL,
        posts_count integer DEFAULT 0,
        reels_count integer DEFAULT 0,
        stories_count integer DEFAULT 0,
        created_at timestamptz DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS chain_content_hashtags (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        hashtag_id uuid REFERENCES chain_hashtags(id) ON DELETE CASCADE,
        content_type text NOT NULL,
        content_id uuid NOT NULL,
        created_at timestamptz DEFAULT now(),
        UNIQUE(hashtag_id, content_type, content_id)
    );
    CREATE TABLE IF NOT EXISTS chain_reels (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        caption text,
        video_url text,
        thumbnail_url text,
        media_url text,
        storage_bucket text,
        storage_path text,
        music_title text,
        status text DEFAULT 'published',
        visibility text DEFAULT 'public',
        processing_status text DEFAULT 'ready',
        views_count integer DEFAULT 0,
        likes_count integer DEFAULT 0,
        comments_count integer DEFAULT 0,
        shares_count integer DEFAULT 0,
        mime_type text,
        file_size bigint,
        created_at timestamptz DEFAULT now(),
        updated_at timestamptz DEFAULT now(),
        deleted_at timestamptz
    );
    ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS music_title text;
    ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS processing_status text DEFAULT 'ready';
    ALTER TABLE chain_reels ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
    CREATE TABLE IF NOT EXISTS chain_follows (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        follower_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        following_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        created_at timestamptz DEFAULT now(),
        UNIQUE(follower_profile_id, following_profile_id)
    );
    CREATE TABLE IF NOT EXISTS chain_post_reactions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        post_id uuid REFERENCES chain_posts(id) ON DELETE CASCADE,
        reaction_type text DEFAULT 'like',
        created_at timestamptz DEFAULT now(),
        UNIQUE(profile_id, post_id, reaction_type)
    );
    CREATE TABLE IF NOT EXISTS chain_reel_reactions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        reel_id uuid REFERENCES chain_reels(id) ON DELETE CASCADE,
        reaction_type text DEFAULT 'like',
        created_at timestamptz DEFAULT now(),
        UNIQUE(profile_id, reel_id, reaction_type)
    );
    CREATE TABLE IF NOT EXISTS chain_story_reactions (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        story_id uuid REFERENCES chain_status_posts(id) ON DELETE CASCADE,
        reaction_type text DEFAULT 'like',
        created_at timestamptz DEFAULT now(),
        UNIQUE(profile_id, story_id, reaction_type)
    );
    CREATE TABLE IF NOT EXISTS chain_post_comments (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        post_id uuid REFERENCES chain_posts(id) ON DELETE CASCADE,
        body text NOT NULL,
        created_at timestamptz DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS chain_reel_comments (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        reel_id uuid REFERENCES chain_reels(id) ON DELETE CASCADE,
        body text NOT NULL,
        created_at timestamptz DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS chain_saved_items (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        item_type text NOT NULL,
        item_id uuid NOT NULL,
        created_at timestamptz DEFAULT now(),
        UNIQUE(profile_id, item_type, item_id)
    );
    CREATE TABLE IF NOT EXISTS chain_notifications (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        recipient_profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
        event_type text,
        title text,
        body text,
        entity_type text,
        entity_id uuid,
        action_url text,
        is_read boolean DEFAULT false,
        created_at timestamptz DEFAULT now(),
        read_at timestamptz,
        deleted_at timestamptz
    );
    CREATE TABLE IF NOT EXISTS chain_notification_events (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        actor_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
        event_type text NOT NULL,
        title text,
        body text,
        target_url text,
        is_read boolean DEFAULT false,
        created_at timestamptz DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS chain_conversations (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_type text DEFAULT 'direct',
        title text,
        created_by uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
        last_message text,
        last_message_at timestamptz,
        created_at timestamptz DEFAULT now()
    );
    CREATE TABLE IF NOT EXISTS chain_conversation_members (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id uuid REFERENCES chain_conversations(id) ON DELETE CASCADE,
        profile_id uuid REFERENCES chain_profiles(id) ON DELETE CASCADE,
        role text DEFAULT 'member',
        joined_at timestamptz DEFAULT now(),
        muted boolean DEFAULT false,
        blocked boolean DEFAULT false,
        UNIQUE(conversation_id, profile_id)
    );
    CREATE TABLE IF NOT EXISTS chain_messages (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        conversation_id uuid REFERENCES chain_conversations(id) ON DELETE CASCADE,
        thread_id uuid,
        sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL,
        message_type text DEFAULT 'text',
        body text,
        media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL,
        media_url text,
        mime_type text,
        is_read boolean DEFAULT false,
        is_seen boolean DEFAULT false,
        is_deleted boolean DEFAULT false,
        delivery_status text DEFAULT 'sent',
        client_event_id text,
        created_at timestamptz DEFAULT now(),
        deleted_at timestamptz
    );
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS conversation_id uuid REFERENCES chain_conversations(id) ON DELETE CASCADE;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS thread_id uuid;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS sender_profile_id uuid REFERENCES chain_profiles(id) ON DELETE SET NULL;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS message_type text DEFAULT 'text';
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS body text;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_upload_id uuid REFERENCES chain_media_uploads(id) ON DELETE SET NULL;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS media_url text;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS mime_type text;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_read boolean DEFAULT false;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_seen boolean DEFAULT false;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS is_deleted boolean DEFAULT false;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS delivery_status text DEFAULT 'sent';
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS client_event_id text;
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS created_at timestamptz DEFAULT now();
    ALTER TABLE chain_messages ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
    CREATE INDEX IF NOT EXISTS idx_chain_posts_feed_real_content ON chain_posts(visibility, deleted_at, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_posts_profile_recent_real_content ON chain_posts(profile_id, deleted_at, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_status_active_real_content ON chain_status_posts(expires_at, deleted_at, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_status_profile_active_real_content ON chain_status_posts(profile_id, expires_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_reels_profile_recent_real_content ON chain_reels(profile_id, deleted_at, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_hashtags_tag ON chain_hashtags(tag);
    CREATE INDEX IF NOT EXISTS idx_chain_follows_follower ON chain_follows(follower_profile_id);
    CREATE INDEX IF NOT EXISTS idx_chain_follows_following ON chain_follows(following_profile_id);
    CREATE INDEX IF NOT EXISTS idx_chain_post_reactions_post ON chain_post_reactions(post_id);
    CREATE INDEX IF NOT EXISTS idx_chain_reel_reactions_reel ON chain_reel_reactions(reel_id);
    CREATE INDEX IF NOT EXISTS idx_chain_story_reactions_story ON chain_story_reactions(story_id);
    CREATE INDEX IF NOT EXISTS idx_chain_post_comments_post ON chain_post_comments(post_id);
    CREATE INDEX IF NOT EXISTS idx_chain_reel_comments_reel ON chain_reel_comments(reel_id);
    CREATE INDEX IF NOT EXISTS idx_chain_saved_items_profile ON chain_saved_items(profile_id);
    CREATE INDEX IF NOT EXISTS idx_chain_notifications_recipient ON chain_notifications(recipient_profile_id, is_read, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_chain_messages_conversation ON chain_messages(conversation_id, created_at);
    """
    try:
        write_query(sql, timeout_ms=10000)
        status = verify_content_tables()
        log_info("content_schema_bootstrap_completed", tables=len(status.get("tables", {})), missing=status.get("missing", []), persistence_mode=_persistence_mode())
        return {"ok": not status.get("missing"), "skipped": False, **status}
    except Exception as error:
        log_error("content_schema_bootstrap_failed", error=error, persistence_mode=_persistence_mode())
        return {"ok": False, "skipped": False, "error": str(error)}


def verify_content_tables():
    if os.getenv("CHAIN_FAST_LOCAL") == "1" and not is_production_env():
        return {"ok": False, "skipped": True, "missing": [], "tables": {}, "reason": "fast_local"}
    rows = fast_query(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = 'public' AND tablename = ANY(%s)
        """,
        (CONTENT_TABLES,),
        timeout_ms=3000,
        default=[],
    )
    existing = {row.get("tablename") for row in rows}
    tables = {name: name in existing for name in CONTENT_TABLES}
    missing = [name for name, exists in tables.items() if not exists]
    return {"ok": not missing, "skipped": False, "missing": missing, "tables": tables}


def _columns(table, fallback):
    columns = set(get_table_columns(table) or [])
    return columns or set(fallback)


def _insert(table, payload, fallback_columns):
    columns = _columns(table, fallback_columns)
    safe_payload = {key: value for key, value in payload.items() if value is not None and key in columns}
    if not safe_payload:
        return None
    cols = list(safe_payload.keys())
    placeholders = ", ".join(["%s"] * len(cols))
    quoted = ", ".join(f'"{col}"' for col in cols)
    query = f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders}) RETURNING *'
    try:
        rows = write_query(query, [safe_payload[col] for col in cols], timeout_ms=5000)
        if rows:
            log_info("content_using_neon_persistence", table=table)
        return rows[0] if isinstance(rows, list) and rows else None
    except Exception as error:
        log_warning("content_db_unavailable", table=table, error=str(error), fallback_allowed=local_fallback_allowed())
        return None


def _insert_media_metadata(media):
    return _insert(
        "chain_media_uploads",
        media,
        ["id", "profile_id", "upload_type", "media_type", "file_path", "public_url", "storage_bucket", "storage_path", "mime_type", "file_size", "original_filename", "created_at"],
    )


def _store_hashtags(tags, content_type, content_id):
    if not tags:
        return
    for tag in tags:
        local = _LOCAL_STORE["hashtags"].setdefault(tag, {"tag": tag, "posts_count": 0, "reels_count": 0, "stories_count": 0})
        count_key = "stories_count" if content_type == "story" else f"{content_type}s_count"
        local[count_key] = local.get(count_key, 0) + 1
        try:
            rows = write_query(
                """
                INSERT INTO chain_hashtags (tag) VALUES (%s)
                ON CONFLICT (tag) DO UPDATE SET
                    posts_count = chain_hashtags.posts_count + %s,
                    reels_count = chain_hashtags.reels_count + %s,
                    stories_count = chain_hashtags.stories_count + %s
                RETURNING id
                """,
                (tag, 1 if content_type == "post" else 0, 1 if content_type == "reel" else 0, 1 if content_type == "story" else 0),
                timeout_ms=3000,
            )
            hashtag_id = rows[0]["id"] if rows else None
            if hashtag_id:
                write_query(
                    """
                    INSERT INTO chain_content_hashtags (hashtag_id, content_type, content_id)
                    VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                    """,
                    (hashtag_id, content_type, content_id),
                    timeout_ms=3000,
                )
        except Exception:
            continue


def create_post_record(profile_id, body="", media_file=None, link_url="", town_tag="", visibility="public"):
    body = sanitize_text(body)
    town_tag = sanitize_text(town_tag, max_len=120)
    visibility = normalize_visibility(visibility)
    link_url = validate_link(link_url)
    media = None
    if media_file and getattr(media_file, "filename", ""):
        media, error = save_media_file(media_file, "post", profile_id=profile_id)
        if error:
            return None, error
    if not body and not media and not link_url:
        return None, "Post cannot be empty."
    media_type = (media or {}).get("media_type")
    post_type = "link" if link_url else (media_type or "text")
    post_id = str(uuid.uuid4())
    now = utcnow().isoformat()
    payload = {
        "id": post_id,
        "profile_id": profile_id,
        "body": body,
        "caption": body,
        "post_type": post_type,
        "media_url": media["public_url"] if media and media_type == "image" else None,
        "video_url": media["public_url"] if media and media_type == "video" else None,
        "link_url": link_url,
        "town_tag": town_tag,
        "visibility": visibility,
        "likes_count": 0,
        "comments_count": 0,
        "shares_count": 0,
        "created_at": now,
    }
    inserted = _insert(
        "chain_posts",
        payload,
        ["id", "profile_id", "body", "caption", "post_type", "media_url", "video_url", "link_url", "town_tag", "visibility", "likes_count", "comments_count", "shares_count", "created_at"],
    )
    if not inserted and is_production_env():
        log_error("content_post_persistence_failed", profile_id=profile_id)
        return None, "Database unavailable. Post was not saved."
    record = inserted or payload
    record["media_url"] = record.get("media_url") or record.get("video_url")
    if not inserted:
        log_warning("content_using_local_fallback", content_type="post", profile_id=profile_id)
        _LOCAL_STORE["posts"].insert(0, record)
    _store_hashtags(parse_hashtags(body), "post", post_id)
    invalidate_content_caches()
    return record, None


def create_reel_record(profile_id, video_file, caption="", music_title="", visibility="public"):
    caption = sanitize_text(caption)
    music_title = sanitize_text(music_title, max_len=160)
    visibility = normalize_visibility(visibility)
    media, error = save_media_file(video_file, "reel", media_kind="video", profile_id=profile_id)
    if error:
        return None, error
    reel_id = str(uuid.uuid4())
    now = utcnow().isoformat()
    payload = {
        "id": reel_id,
        "profile_id": profile_id,
        "caption": caption,
        "video_url": media["public_url"],
        "media_url": media["public_url"],
        "storage_bucket": "local",
        "storage_path": media["file_path"],
        "music_title": music_title,
        "status": "published",
        "visibility": visibility,
        "processing_status": "ready",
        "mime_type": media["mime_type"],
        "file_size": media["file_size"],
        "likes_count": 0,
        "comments_count": 0,
        "shares_count": 0,
        "views_count": 0,
        "created_at": now,
    }
    inserted = _insert(
        "chain_reels",
        payload,
        ["id", "profile_id", "caption", "video_url", "media_url", "storage_bucket", "storage_path", "music_title", "status", "visibility", "processing_status", "mime_type", "file_size", "likes_count", "comments_count", "shares_count", "views_count", "created_at"],
    )
    if not inserted and is_production_env():
        log_error("content_reel_persistence_failed", profile_id=profile_id)
        return None, "Database unavailable. Reel was not saved."
    record = inserted or payload
    if not inserted:
        log_warning("content_using_local_fallback", content_type="reel", profile_id=profile_id)
        _LOCAL_STORE["reels"].insert(0, record)
    _store_hashtags(parse_hashtags(caption), "reel", reel_id)
    invalidate_content_caches()
    return record, None


def create_story_record(profile_id, caption="", media_file=None, visibility="public"):
    caption = sanitize_text(caption)
    visibility = normalize_visibility(visibility)
    media = None
    if media_file and getattr(media_file, "filename", ""):
        media, error = save_media_file(media_file, "story", profile_id=profile_id)
        if error:
            return None, error
    if not caption and not media:
        return None, "Story cannot be empty."
    media_type = (media or {}).get("media_type")
    story_id = str(uuid.uuid4())
    now = utcnow()
    payload = {
        "id": story_id,
        "profile_id": profile_id,
        "status_type": "story",
        "caption": caption,
        "media_url": media["public_url"] if media and media_type == "image" else None,
        "video_url": media["public_url"] if media and media_type == "video" else None,
        "visibility": visibility,
        "expires_at": (now + timedelta(hours=24)).isoformat(),
        "likes_count": 0,
        "created_at": now.isoformat(),
    }
    inserted = _insert(
        "chain_status_posts",
        payload,
        ["id", "profile_id", "status_type", "caption", "media_url", "video_url", "visibility", "expires_at", "likes_count", "created_at"],
    )
    if not inserted and is_production_env():
        log_error("content_story_persistence_failed", profile_id=profile_id)
        return None, "Database unavailable. Story was not saved."
    record = inserted or payload
    record["media_url"] = record.get("media_url") or record.get("video_url")
    if not inserted:
        log_warning("content_using_local_fallback", content_type="story", profile_id=profile_id)
        _LOCAL_STORE["stories"].insert(0, record)
    _store_hashtags(parse_hashtags(caption), "story", story_id)
    invalidate_content_caches()
    return record, None


def recent_content_counts():
    counts = {}
    for table in ("chain_posts", "chain_reels", "chain_status_posts", "chain_media_uploads", "chain_hashtags"):
        rows = fast_query(f"SELECT COUNT(*) AS count FROM {table}", timeout_ms=1500, default=[])
        counts[table] = int(rows[0].get("count") or 0) if rows else 0
    if not any(counts.values()) and local_fallback_allowed():
        counts.update({
            "local_posts": len(_LOCAL_STORE["posts"]),
            "local_reels": len(_LOCAL_STORE["reels"]),
            "local_stories": len(_LOCAL_STORE["stories"]),
            "local_media": len(_LOCAL_STORE["media"]),
            "local_hashtags": len(_LOCAL_STORE["hashtags"]),
        })
    return counts


def upload_folder_status():
    status = {}
    for key, folder in UPLOAD_FOLDERS.items():
        os.makedirs(folder, exist_ok=True)
        status[key] = {
            "path": folder,
            "exists": os.path.isdir(folder),
            "writable": os.access(folder, os.W_OK),
        }
    return status


def invalidate_content_caches():
    delete_cache(cache_key("chain_homepage_v3", "public"))


def local_content():
    return _LOCAL_STORE


def active_local_stories(profile_id=None):
    now = utcnow()
    items = []
    for story in _LOCAL_STORE["stories"]:
        if profile_id and story.get("profile_id") != profile_id:
            continue
        expires_at = story.get("expires_at")
        parsed = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) if expires_at else now
        if parsed > now:
            items.append(story)
    return items


def search_hashtags(query):
    tag = (query or "").strip().lstrip("#").lower()
    rows = []
    if tag:
        rows = fast_query(
            "SELECT tag, posts_count, reels_count, stories_count FROM chain_hashtags WHERE tag ILIKE %s ORDER BY posts_count DESC LIMIT 20",
            (f"%{tag}%",),
            timeout_ms=1500,
            default=[],
        )
    if rows:
        return rows
    return [value for key, value in _LOCAL_STORE["hashtags"].items() if not tag or tag in key]
