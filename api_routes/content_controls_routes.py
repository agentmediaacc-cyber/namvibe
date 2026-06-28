from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from api_routes.profile_routes import login_required
from services.neon_service import fast_query, write_query, get_cached_table_columns
from services.profile_service import get_current_profile

content_controls_bp = Blueprint("content_controls", __name__)

CONTENT_TABLES = {
    "post": "chain_posts",
    "reel": "chain_reels",
    "story": "chain_status_posts",
}

CONTENT_VISIBILITY_OPTIONS = {"public", "followers", "private", "subscribers"}


def _get_table(content_type):
    table = CONTENT_TABLES.get(content_type)
    if not table:
        raise ValueError(f"Invalid content_type: {content_type}")
    return table


def _table_columns(table):
    cols = get_cached_table_columns(table)
    return cols if cols is not None else set()


def _has_column(table, column):
    return column in _table_columns(table)


def _verify_owner(content_type, content_id, profile_id):
    table = _get_table(content_type)
    where_deleted = "AND deleted_at IS NULL" if _has_column(table, "deleted_at") else ""
    row = fast_query(
        f"SELECT profile_id FROM {table} WHERE id = %s {where_deleted} LIMIT 1",
        (content_id,),
        default=None,
    )
    if not row:
        return None
    if row[0]["profile_id"] != profile_id:
        return False
    return row[0]


def _make_share_url(content_type, content_id):
    path_map = {"post": "posts", "reel": "reels", "story": "stories"}
    return f"/{path_map.get(content_type, content_type)}/{content_id}"


def _pick_text_column(table):
    for col in ("caption", "body", "description"):
        if _has_column(table, col):
            return col
    return None


@content_controls_bp.route("/api/content/<content_type>/<content_id>/caption", methods=["PUT"])
@login_required
def edit_caption(content_type, content_id):
    try:
        if content_type not in CONTENT_TABLES:
            return jsonify({"error": "Invalid content_type"}), 400
        profile = get_current_profile()
        profile_id = profile.get("id") if profile else None
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        owner_check = _verify_owner(content_type, content_id, profile_id)
        if owner_check is None:
            return jsonify({"error": "Content not found"}), 404
        if owner_check is False:
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json(silent=True) or {}
        value = data.get("caption", "")
        table = _get_table(content_type)
        text_col = _pick_text_column(table)
        if not text_col:
            return jsonify({"error": "Table has no text column (caption/body/description)"}), 400
        sets = [f"{text_col} = %s"]
        params = [value]
        if _has_column(table, "updated_at"):
            sets.append("updated_at = %s")
            params.append(datetime.now(timezone.utc))
        params.append(content_id)
        write_query(
            f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@content_controls_bp.route("/api/content/<content_type>/<content_id>", methods=["DELETE"])
@login_required
def delete_content(content_type, content_id):
    try:
        if content_type not in CONTENT_TABLES:
            return jsonify({"error": "Invalid content_type"}), 400
        profile = get_current_profile()
        profile_id = profile.get("id") if profile else None
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        owner_check = _verify_owner(content_type, content_id, profile_id)
        if owner_check is None:
            return jsonify({"error": "Content not found"}), 404
        if owner_check is False:
            return jsonify({"error": "Forbidden"}), 403
        table = _get_table(content_type)
        if not _has_column(table, "deleted_at"):
            return jsonify({"error": f"Soft delete not supported for {table}"}), 400
        sets = ["deleted_at = %s"]
        params = [datetime.now(timezone.utc)]
        if _has_column(table, "updated_at"):
            sets.append("updated_at = %s")
            params.append(datetime.now(timezone.utc))
        params.append(content_id)
        write_query(
            f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@content_controls_bp.route("/api/content/<content_type>/<content_id>/visibility", methods=["PUT"])
@login_required
def change_visibility(content_type, content_id):
    try:
        if content_type not in CONTENT_TABLES:
            return jsonify({"error": "Invalid content_type"}), 400
        profile = get_current_profile()
        profile_id = profile.get("id") if profile else None
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        owner_check = _verify_owner(content_type, content_id, profile_id)
        if owner_check is None:
            return jsonify({"error": "Content not found"}), 404
        if owner_check is False:
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json(silent=True) or {}
        visibility = data.get("visibility", "")
        if visibility not in CONTENT_VISIBILITY_OPTIONS:
            return jsonify({"error": f"Invalid visibility. Must be one of: {', '.join(CONTENT_VISIBILITY_OPTIONS)}"}), 400
        table = _get_table(content_type)
        if not _has_column(table, "visibility"):
            return jsonify({"error": f"Visibility column does not exist on {table}"}), 400
        sets = ["visibility = %s"]
        params = [visibility]
        if _has_column(table, "updated_at"):
            sets.append("updated_at = %s")
            params.append(datetime.now(timezone.utc))
        params.append(content_id)
        write_query(
            f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s",
            tuple(params),
        )
        return jsonify({"ok": True, "visibility": visibility})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@content_controls_bp.route("/api/content/<content_type>/<content_id>/lock", methods=["POST"])
@login_required
def toggle_lock(content_type, content_id):
    try:
        if content_type not in CONTENT_TABLES:
            return jsonify({"error": "Invalid content_type"}), 400
        profile = get_current_profile()
        profile_id = profile.get("id") if profile else None
        if not profile_id:
            return jsonify({"error": "Unauthorized"}), 401
        owner_check = _verify_owner(content_type, content_id, profile_id)
        if owner_check is None:
            return jsonify({"error": "Content not found"}), 404
        if owner_check is False:
            return jsonify({"error": "Forbidden"}), 403
        data = request.get_json(silent=True) or {}
        locked = bool(data.get("locked", False))
        table = _get_table(content_type)

        if _has_column(table, "locked"):
            sets = ["locked = %s"]
            params = [locked]
            if _has_column(table, "updated_at"):
                sets.append("updated_at = %s")
                params.append(datetime.now(timezone.utc))
            params.append(content_id)
            write_query(
                f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s",
                tuple(params),
            )
        elif _has_column(table, "metadata"):
            where_deleted = "AND deleted_at IS NULL" if _has_column(table, "deleted_at") else ""
            existing = fast_query(
                f"SELECT metadata FROM {table} WHERE id = %s {where_deleted} LIMIT 1",
                (content_id,),
                default=None,
            )
            metadata = {}
            if existing and existing[0].get("metadata"):
                import json
                metadata = json.loads(existing[0]["metadata"]) if isinstance(existing[0]["metadata"], str) else existing[0]["metadata"]
            metadata["locked"] = locked
            sets = ["metadata = %s::jsonb"]
            params = [json.dumps(metadata)]
            if _has_column(table, "updated_at"):
                sets.append("updated_at = %s")
                params.append(datetime.now(timezone.utc))
            params.append(content_id)
            write_query(
                f"UPDATE {table} SET {', '.join(sets)} WHERE id = %s",
                tuple(params),
            )
        else:
            return jsonify({"error": f"Cannot lock content: {table} has no locked or metadata column"}), 400
        return jsonify({"ok": True, "locked": locked})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@content_controls_bp.route("/api/content/<content_type>/<content_id>/share-url", methods=["GET"])
def get_share_url(content_type, content_id):
    try:
        if content_type not in CONTENT_TABLES:
            return jsonify({"error": "Invalid content_type"}), 400
        table = _get_table(content_type)
        where_deleted = "AND deleted_at IS NULL" if _has_column(table, "deleted_at") else ""
        row = fast_query(
            f"SELECT id FROM {table} WHERE id = %s {where_deleted} LIMIT 1",
            (content_id,),
            default=None,
        )
        if not row:
            return jsonify({"error": "Content not found"}), 404
        share_url = _make_share_url(content_type, content_id)
        return jsonify({"ok": True, "share_url": share_url, "content_id": content_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@content_controls_bp.route("/api/content/<content_type>/<content_id>", methods=["GET"])
def get_content(content_type, content_id):
    try:
        if content_type not in CONTENT_TABLES:
            return jsonify({"error": "Invalid content_type"}), 400
        table = _get_table(content_type)
        where_deleted = "AND deleted_at IS NULL" if _has_column(table, "deleted_at") else ""
        row = fast_query(
            f"SELECT * FROM {table} WHERE id = %s {where_deleted} LIMIT 1",
            (content_id,),
            default=None,
        )
        if not row:
            return jsonify({"error": "Content not found"}), 404
        item = row[0]
        if _has_column(table, "visibility"):
            visibility = item.get("visibility", "public")
            if visibility in ("private", "followers"):
                profile = get_current_profile()
                viewer_id = profile.get("id") if profile else None
                if not viewer_id:
                    return jsonify({"error": "Authentication required to view this content"}), 401
                if item.get("profile_id") != viewer_id:
                    if visibility == "private":
                        return jsonify({"error": "This content is private"}), 403
                    from services.neon_service import fast_query as fq
                    where_follow_deleted = "AND deleted_at IS NULL" if _has_column("chain_follows", "deleted_at") else ""
                    following = fq(
                        f"SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s {where_follow_deleted} LIMIT 1",
                        (viewer_id, item["profile_id"]),
                        default=None,
                    )
                    if not following:
                        return jsonify({"error": "This content is for followers only"}), 403
        return jsonify(item)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
