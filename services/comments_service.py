"""Unified comments service — Facebook-level nested comments, reactions, GIFs, pins."""
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query

def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()

COMMENT_TABLES = {
    "post": "chain_post_comments",
    "reel": "chain_reel_comments",
    "story": "chain_status_posts", # actually comments are in chain_comments now
    "live": "chain_live_comments",
}
COMMENT_COUNT_COLUMNS = {
    "post": ("chain_posts", "comments_count"),
    "reel": ("chain_reels", "comments_count"),
    "story": ("chain_status_posts", "comments_count"),
    "live": ("chain_live_rooms", "comments_count"),
}

LEGACY_COMMENT_CONFIG = {
    "post": ("chain_post_comments", "post_id"),
    "reel": ("chain_reel_comments", "reel_id"),
    "live": ("chain_live_comments", "room_id"),
}

def _update_count(content_type, content_id):
    entry = COMMENT_COUNT_COLUMNS.get(content_type)
    if not entry:
        return
    table, col = entry
    legacy = LEGACY_COMMENT_CONFIG.get(content_type)
    if legacy:
        comment_table, entity_col = legacy
        count = fast_query(
            f"SELECT COUNT(*) AS cnt FROM {comment_table} WHERE {entity_col} = %s",
            (content_id,), timeout_ms=2000, default=[{"cnt": 0}]
        )
    else:
        count = fast_query(
            "SELECT COUNT(*) AS cnt FROM chain_comments WHERE content_type = %s AND content_id = %s AND is_deleted = FALSE AND parent_id IS NULL",
            (content_type, content_id), timeout_ms=2000, default=[{"cnt": 0}]
        )
    c = count[0]["cnt"] if count else 0
    try:
        write_query(f"UPDATE {table} SET {col} = %s WHERE id = %s", (c, content_id))
    except Exception:
        pass

def get_comments(content_type, content_id, limit=30):
    legacy = LEGACY_COMMENT_CONFIG.get(content_type)
    if legacy:
        table, entity_col = legacy
        rows = fast_query(f"""
            SELECT c.id, c.profile_id AS user_id, c.body, c.created_at,
                   p.username, p.avatar_url, p.is_verified,
                   0 AS reaction_count,
                   FALSE AS is_pinned
            FROM {table} c
            LEFT JOIN chain_profiles p ON c.profile_id = p.id
            WHERE c.{entity_col} = %s
            ORDER BY c.created_at ASC
            LIMIT %s
        """, (content_id, limit), timeout_ms=2000, default=[])
        return rows or []
    rows = fast_query("""
        SELECT c.*, p.username, p.avatar_url, p.is_verified,
               (SELECT COUNT(*) FROM chain_comment_reactions WHERE comment_id = c.id) AS reaction_count
        FROM chain_comments c
        JOIN chain_profiles p ON c.user_id = p.id
        WHERE c.content_type = %s AND c.content_id = %s AND c.is_deleted = FALSE
        ORDER BY c.is_pinned DESC, c.created_at ASC
        LIMIT %s
    """, (content_type, content_id, limit), timeout_ms=2000, default=[])
    return rows or []

def get_replies(comment_id, limit=20):
    rows = fast_query("""
        SELECT c.*, p.username, p.avatar_url, p.is_verified
        FROM chain_comments c
        JOIN chain_profiles p ON c.user_id = p.id
        WHERE c.parent_id = %s AND c.is_deleted = FALSE
        ORDER BY c.created_at ASC
        LIMIT %s
    """, (comment_id, limit), timeout_ms=2000, default=[])
    return rows or []

def get_replies_for_comments(comment_ids, limit_per_comment=5):
    ids = [str(comment_id) for comment_id in (comment_ids or []) if comment_id]
    if not ids:
        return {}
    rows = fast_query("""
        WITH ranked AS (
            SELECT c.*, p.username, p.avatar_url, p.is_verified,
                   ROW_NUMBER() OVER (PARTITION BY c.parent_id ORDER BY c.created_at ASC) AS reply_rank
            FROM chain_comments c
            JOIN chain_profiles p ON c.user_id = p.id
            WHERE c.parent_id = ANY(%s) AND c.is_deleted = FALSE
        )
        SELECT *
        FROM ranked
        WHERE reply_rank <= %s
        ORDER BY parent_id, created_at ASC
    """, (ids, limit_per_comment), timeout_ms=2000, default=[])
    grouped = {comment_id: [] for comment_id in ids}
    for row in rows or []:
        grouped.setdefault(str(row.get("parent_id")), []).append(row)
    return grouped

def add_comment(content_type, content_id, user_id, body, media_url=None, gif_url=None, parent_id=None):
    import uuid
    clean = " ".join((body or "").strip().split())[:2000]
    if not clean:
        return None
    legacy = LEGACY_COMMENT_CONFIG.get(content_type)
    if legacy and not parent_id:
        table, entity_col = legacy
        comment_id = str(uuid.uuid4())
        try:
            write_query(f"""
                INSERT INTO {table} (id, profile_id, {entity_col}, body)
                VALUES (%s, %s, %s, %s)
            """, (comment_id, user_id, content_id, clean))
            _update_count(content_type, content_id)
            return comment_id
        except Exception:
            return None
    comment_id = str(uuid.uuid4())
    try:
        write_query("""
            INSERT INTO chain_comments (id, content_type, content_id, user_id, body, media_url, gif_url, parent_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (comment_id, content_type, content_id, user_id, clean, media_url, gif_url, parent_id))
        _update_count(content_type, content_id)
        return comment_id
    except Exception:
        return None

def react_to_comment(comment_id, user_id, reaction_type="like"):
    comment = fast_query(
        "SELECT user_id FROM chain_comments WHERE id = %s AND is_deleted = FALSE",
        (comment_id,), timeout_ms=2000, default=[]
    )
    if not comment:
        for table in ("chain_post_comments", "chain_reel_comments", "chain_live_comments"):
            comment = fast_query(
                f"SELECT profile_id AS user_id FROM {table} WHERE id = %s",
                (comment_id,), timeout_ms=1000, default=[]
            )
            if comment:
                break
    if comment:
        author_id = comment[0].get("user_id")
        if author_id and str(author_id) == str(user_id):
            return {"reacted": False, "error": "cannot_like_own_comment"}
    existing = fast_query(
        "SELECT id FROM chain_comment_reactions WHERE comment_id = %s AND user_id = %s AND reaction_type = %s",
        (comment_id, user_id, reaction_type), timeout_ms=2000, default=[]
    )
    if existing:
        write_query("DELETE FROM chain_comment_reactions WHERE id = %s", (existing[0]["id"],))
        return {"reacted": False}
    try:
        write_query(
            "INSERT INTO chain_comment_reactions (comment_id, user_id, reaction_type) VALUES (%s, %s, %s)",
            (comment_id, user_id, reaction_type)
        )
        return {"reacted": True}
    except Exception:
        return {"reacted": False}

def pin_comment(comment_id, user_id):
    comment = fast_query("SELECT * FROM chain_comments WHERE id = %s", (comment_id,), timeout_ms=2000, default=[])
    if not comment:
        return False
    try:
        write_query("UPDATE chain_comments SET is_pinned = NOT is_pinned WHERE id = %s", (comment_id,))
        return True
    except Exception:
        return False

def edit_comment(comment_id, user_id, new_body):
    clean = " ".join((new_body or "").strip().split())[:2000]
    if not clean:
        return False
    try:
        write_query(
            "UPDATE chain_comments SET body = %s, updated_at = now() WHERE id = %s AND user_id = %s AND is_deleted = FALSE",
            (clean, comment_id, user_id)
        )
        return True
    except Exception:
        for table in ("chain_post_comments", "chain_reel_comments", "chain_live_comments"):
            try:
                write_query(
                    f"UPDATE {table} SET body = %s WHERE id = %s AND profile_id = %s",
                    (clean, comment_id, user_id),
                )
                return True
            except Exception:
                continue
        return False

def delete_comment(comment_id, user_id, is_admin=False):
    try:
        if is_admin:
            write_query("UPDATE chain_comments SET is_deleted = TRUE WHERE id = %s", (comment_id,))
        else:
            write_query("UPDATE chain_comments SET is_deleted = TRUE WHERE id = %s AND user_id = %s", (comment_id, user_id))
        return True
    except Exception:
        for table in ("chain_post_comments", "chain_reel_comments", "chain_live_comments"):
            try:
                if is_admin:
                    write_query(f"DELETE FROM {table} WHERE id = %s", (comment_id,))
                else:
                    write_query(f"DELETE FROM {table} WHERE id = %s AND profile_id = %s", (comment_id, user_id))
                return True
            except Exception:
                continue
    return False
