"""Gallery service — profile media gallery with albums/folders.
All metadata stored in Neon; media files stored in Supabase Storage."""

import uuid
from datetime import datetime, timedelta, timezone

from services.neon_service import fast_query, write_query, get_table_columns
from services.content_service import save_media_file, _insert, _LOCAL_STORE, _insert_media_metadata as _media_meta_insert
from services.logging_service import log_info, log_error, log_warning
from services.supabase_storage_service import get_supabase_admin


VISIBILITIES = {"public", "followers", "private"}
ALBUM_COLUMNS = ["id", "profile_id", "title", "description", "visibility", "cover_url", "created_at", "updated_at"]
MEDIA_COLUMNS = ["id", "profile_id", "upload_type", "media_type", "file_path", "public_url", "storage_bucket", "storage_path", "mime_type", "file_size", "size_bytes", "original_filename", "album_id", "visibility", "created_at"]


def utcnow():
    return datetime.now(timezone.utc)


def normalize_visibility(value):
    value = (value or "public").strip().lower()
    return value if value in VISIBILITIES else "public"


def _is_follower(follower_id, profile_id):
    rows = fast_query(
        "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
        (follower_id, profile_id),
        timeout_ms=2000,
        default=[],
    )
    return bool(rows)


def _visibility_view(viewer_id, profile_id):
    if viewer_id and str(viewer_id) == str(profile_id):
        return None
    if viewer_id and _is_follower(viewer_id, profile_id):
        return ["public", "followers"]
    return ["public"]


def create_album(profile_id, title, description="", visibility="public"):
    try:
        title = (title or "").strip()[:100]
        if not title:
            return None, "Album title is required."
        description = (description or "").strip()[:500]
        visibility = normalize_visibility(visibility)
        album_id = str(uuid.uuid4())
        now = utcnow().isoformat()
        payload = {
            "id": album_id,
            "profile_id": profile_id,
            "title": title,
            "description": description,
            "visibility": visibility,
            "cover_url": None,
            "created_at": now,
            "updated_at": now,
        }
        inserted = _insert("chain_media_albums", payload, ALBUM_COLUMNS)
        if inserted:
            log_info("gallery_album_created", album_id=album_id, profile_id=profile_id)
            return inserted, None
        log_warning("gallery_album_local_fallback", profile_id=profile_id)
        _LOCAL_STORE.setdefault("albums", []).append(payload)
        return payload, None
    except Exception as e:
        log_error("gallery_create_album_failed", profile_id=profile_id, error=str(e))
        return None, str(e)


def get_albums(profile_id, viewer_id=None):
    try:
        vis_filter = _visibility_view(viewer_id, profile_id)
        if vis_filter is None:
            rows = fast_query(
                """
                SELECT a.*, p.username, p.display_name, p.avatar_url
                FROM chain_media_albums a
                LEFT JOIN chain_profiles p ON a.profile_id = p.id
                WHERE a.profile_id = %s
                ORDER BY a.created_at DESC
                """,
                (profile_id,),
                timeout_ms=5000,
                default=[],
            )
        else:
            placeholders = ", ".join(["%s"] * len(vis_filter))
            rows = fast_query(
                f"""
                SELECT a.*, p.username, p.display_name, p.avatar_url
                FROM chain_media_albums a
                LEFT JOIN chain_profiles p ON a.profile_id = p.id
                WHERE a.profile_id = %s AND a.visibility IN ({placeholders})
                ORDER BY a.created_at DESC
                """,
                (profile_id, *vis_filter),
                timeout_ms=5000,
                default=[],
            )
        return rows or []
    except Exception as e:
        log_error("gallery_get_albums_failed", profile_id=profile_id, error=str(e))
        return []


def get_album(album_id, viewer_id=None):
    try:
        rows = fast_query(
            """
            SELECT a.*, p.username, p.display_name, p.avatar_url,
                (SELECT COUNT(*) FROM chain_media_uploads m WHERE m.album_id = a.id) AS item_count
            FROM chain_media_albums a
            LEFT JOIN chain_profiles p ON a.profile_id = p.id
            WHERE a.id = %s
            LIMIT 1
            """,
            (album_id,),
            timeout_ms=3000,
            default=[],
        )
        if not rows:
            return None
        album = rows[0]
        owner_id = album.get("profile_id")
        if viewer_id and str(viewer_id) == str(owner_id):
            return album
        if album.get("visibility") == "private":
            return None
        if album.get("visibility") == "followers":
            if viewer_id and _is_follower(viewer_id, owner_id):
                return album
            return None
        return album
    except Exception as e:
        log_error("gallery_get_album_failed", album_id=album_id, error=str(e))
        return None


def update_album(album_id, profile_id, **updates):
    try:
        rows = fast_query(
            "SELECT id FROM chain_media_albums WHERE id = %s AND profile_id = %s LIMIT 1",
            (album_id, profile_id),
            timeout_ms=2000,
            default=[],
        )
        if not rows:
            return None, "Album not found or you do not own it."

        allowed = {"title", "description", "visibility", "cover_url"}
        safe = {}
        for key, value in updates.items():
            if key not in allowed or value is None:
                continue
            if key == "title":
                value = str(value).strip()[:100]
            elif key == "description":
                value = str(value).strip()[:500]
            elif key == "visibility":
                value = normalize_visibility(value)
            safe[key] = value

        if not safe:
            return None, "No valid fields to update."

        safe["updated_at"] = utcnow().isoformat()
        set_parts = ", ".join(f'"{col}" = %s' for col in safe)
        values = list(safe.values())
        values.append(album_id)

        updated = write_query(
            f"UPDATE chain_media_albums SET {set_parts} WHERE id = %s RETURNING *",
            values,
            timeout_ms=3000,
        )
        if updated:
            log_info("gallery_album_updated", album_id=album_id)
            return updated[0], None
        return None, "Album could not be updated."
    except Exception as e:
        log_error("gallery_update_album_failed", album_id=album_id, error=str(e))
        return None, str(e)


def delete_album(album_id, profile_id):
    try:
        rows = fast_query(
            "SELECT id FROM chain_media_albums WHERE id = %s AND profile_id = %s LIMIT 1",
            (album_id, profile_id),
            timeout_ms=2000,
            default=[],
        )
        if not rows:
            return False, "Album not found or you do not own it."

        write_query(
            "UPDATE chain_media_uploads SET album_id = NULL WHERE album_id = %s",
            (album_id,),
            timeout_ms=3000,
        )
        write_query(
            "DELETE FROM chain_media_albums WHERE id = %s",
            (album_id,),
            timeout_ms=3000,
        )
        log_info("gallery_album_deleted", album_id=album_id)
        return True, None
    except Exception as e:
        log_error("gallery_delete_album_failed", album_id=album_id, error=str(e))
        return False, str(e)


def add_media_to_album(album_id, media_id, profile_id):
    try:
        album = fast_query(
            "SELECT id, profile_id FROM chain_media_albums WHERE id = %s LIMIT 1",
            (album_id,),
            timeout_ms=2000,
            default=[],
        )
        if not album:
            return False, "Album not found."
        if str(album[0]["profile_id"]) != str(profile_id):
            return False, "You do not own this album."

        media = fast_query(
            "SELECT id, profile_id FROM chain_media_uploads WHERE id = %s LIMIT 1",
            (media_id,),
            timeout_ms=2000,
            default=[],
        )
        if not media:
            return False, "Media not found."
        if str(media[0]["profile_id"]) != str(profile_id):
            return False, "You do not own this media item."

        write_query(
            "UPDATE chain_media_uploads SET album_id = %s WHERE id = %s",
            (album_id, media_id),
            timeout_ms=3000,
        )
        log_info("gallery_media_added_to_album", media_id=media_id, album_id=album_id)
        return True, None
    except Exception as e:
        log_error("gallery_add_media_to_album_failed", media_id=media_id, album_id=album_id, error=str(e))
        return False, str(e)


def remove_media_from_album(media_id, profile_id):
    try:
        media = fast_query(
            "SELECT id, profile_id FROM chain_media_uploads WHERE id = %s LIMIT 1",
            (media_id,),
            timeout_ms=2000,
            default=[],
        )
        if not media:
            return False, "Media not found."
        if str(media[0]["profile_id"]) != str(profile_id):
            return False, "You do not own this media item."

        write_query(
            "UPDATE chain_media_uploads SET album_id = NULL WHERE id = %s",
            (media_id,),
            timeout_ms=3000,
        )
        log_info("gallery_media_removed_from_album", media_id=media_id)
        return True, None
    except Exception as e:
        log_error("gallery_remove_media_from_album_failed", media_id=media_id, error=str(e))
        return False, str(e)


def get_profile_gallery(profile_id, viewer_id=None, album_id=None, media_type=None, page=1, per_page=20):
    try:
        vis_filter = _visibility_view(viewer_id, profile_id)
        conditions = ["m.profile_id = %s"]
        params = [profile_id]

        if vis_filter is not None:
            placeholders = ", ".join(["%s"] * len(vis_filter))
            conditions.append(f"m.visibility IN ({placeholders})")
            params.extend(vis_filter)

        if album_id:
            conditions.append("m.album_id = %s")
            params.append(album_id)

        if media_type:
            conditions.append("m.media_type = %s")
            params.append(media_type)

        where = " AND ".join(conditions)

        count_rows = fast_query(
            f"SELECT COUNT(*) AS count FROM chain_media_uploads m WHERE {where}",
            params,
            timeout_ms=3000,
            default=[{"count": 0}],
        )
        total = int(count_rows[0]["count"]) if count_rows else 0

        offset = (page - 1) * per_page
        items = fast_query(
            f"""
            SELECT m.*, p.username, p.display_name, p.avatar_url
            FROM chain_media_uploads m
            LEFT JOIN chain_profiles p ON m.profile_id = p.id
            WHERE {where}
            ORDER BY m.created_at DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, offset],
            timeout_ms=5000,
            default=[],
        )

        return (items or [], total)
    except Exception as e:
        log_error("gallery_get_profile_gallery_failed", profile_id=profile_id, error=str(e))
        return ([], 0)


def get_profile_media_stats(profile_id):
    try:
        def count_q(sql, params=None):
            rows = fast_query(sql, params or (profile_id,), timeout_ms=2000, default=[{"count": 0}])
            return int(rows[0]["count"]) if rows else 0

        total_media = count_q("SELECT COUNT(*) AS count FROM chain_media_uploads WHERE profile_id = %s")
        total_albums = count_q("SELECT COUNT(*) AS count FROM chain_media_albums WHERE profile_id = %s")
        total_posts = count_q("SELECT COUNT(*) AS count FROM chain_posts WHERE profile_id = %s AND deleted_at IS NULL")
        total_reels = count_q("SELECT COUNT(*) AS count FROM chain_reels WHERE profile_id = %s AND deleted_at IS NULL")
        active_stories = count_q(
            "SELECT COUNT(*) AS count FROM chain_status_posts WHERE profile_id = %s AND status_type = 'story' AND deleted_at IS NULL AND expires_at > now()"
        )
        public_count = count_q(
            "SELECT COUNT(*) AS count FROM chain_media_uploads WHERE profile_id = %s AND visibility = 'public'"
        )
        followers_count = count_q(
            "SELECT COUNT(*) AS count FROM chain_media_uploads WHERE profile_id = %s AND visibility = 'followers'"
        )
        private_count = count_q(
            "SELECT COUNT(*) AS count FROM chain_media_uploads WHERE profile_id = %s AND visibility = 'private'"
        )

        return {
            "total_media": total_media,
            "total_albums": total_albums,
            "total_posts": total_posts,
            "total_reels": total_reels,
            "active_stories": active_stories,
            "public_count": public_count,
            "followers_count": followers_count,
            "private_count": private_count,
        }
    except Exception as e:
        log_error("gallery_get_profile_media_stats_failed", profile_id=profile_id, error=str(e))
        return {}


def toggle_media_visibility(media_id, profile_id, visibility):
    try:
        visibility = normalize_visibility(visibility)
        tables = ["chain_media_uploads", "chain_posts", "chain_reels", "chain_status_posts"]
        for table in tables:
            rows = write_query(
                f"UPDATE {table} SET visibility = %s WHERE id = %s AND profile_id = %s RETURNING *",
                (visibility, media_id, profile_id),
                timeout_ms=3000,
            )
            if rows:
                log_info("gallery_media_visibility_toggled", media_id=media_id, table=table, visibility=visibility)
                return rows[0], None
        return None, "Media not found or you do not own it."
    except Exception as e:
        log_error("gallery_toggle_media_visibility_failed", media_id=media_id, error=str(e))
        return None, str(e)


def delete_media(media_id, profile_id):
    try:
        tables = [
            ("chain_media_uploads", "storage_bucket", "storage_path"),
            ("chain_posts", "media_bucket", "media_path"),
            ("chain_reels", "storage_bucket", "storage_path"),
            ("chain_status_posts", "storage_bucket", "storage_path"),
        ]
        for table, bucket_col, path_col in tables:
            rows = fast_query(
                f"SELECT * FROM {table} WHERE id = %s AND profile_id = %s LIMIT 1",
                (media_id, profile_id),
                timeout_ms=2000,
                default=[],
            )
            if rows:
                record = rows[0]
                bucket = record.get(bucket_col)
                path = record.get(path_col)
                if bucket and path:
                    try:
                        supabase = get_supabase_admin()
                        supabase.storage.from_(bucket).remove([path])
                        log_info("gallery_storage_deleted", bucket=bucket, path=path)
                    except Exception as se:
                        log_warning("gallery_storage_delete_failed", media_id=media_id, error=str(se))

                write_query(f"DELETE FROM {table} WHERE id = %s", (media_id,), timeout_ms=3000)
                log_info("gallery_media_deleted", media_id=media_id, table=table)
                return True, None

        return False, "Media not found or you do not own it."
    except Exception as e:
        log_error("gallery_delete_media_failed", media_id=media_id, error=str(e))
        return False, str(e)
