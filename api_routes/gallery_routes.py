from flask import Blueprint, request, jsonify, render_template, redirect
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_profile_by_id, get_profile_privacy
from services.gallery_service import (
    create_album,
    get_albums,
    update_album,
    delete_album,
    add_media_to_album,
    remove_media_from_album,
    get_profile_gallery,
    get_profile_media_stats,
    toggle_media_visibility,
    delete_media,
)
from services.gallery_service import get_album as get_album_by_id
from services.neon_service import fast_query

gallery_bp = Blueprint("gallery", __name__, url_prefix="/gallery")


@gallery_bp.route("/api/gallery/<profile_id>")
@login_required
def api_gallery(profile_id):
    try:
        viewer = get_current_profile()
        viewer_id = viewer.get("id") if viewer else None
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 50)
        album_id = request.args.get("album_id")
        media_type = request.args.get("media_type")
        items, total = get_profile_gallery(
            profile_id,
            viewer_id=viewer_id,
            album_id=album_id,
            media_type=media_type,
            page=page,
            per_page=per_page,
        )
        return jsonify({"ok": True, "items": items, "total": total, "page": page, "per_page": per_page})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/albums/<profile_id>")
@login_required
def api_albums(profile_id):
    try:
        viewer = get_current_profile()
        viewer_id = viewer.get("id") if viewer else None
        albums = get_albums(profile_id, viewer_id=viewer_id)
        return jsonify({"ok": True, "albums": albums})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/albums/create", methods=["POST"])
@login_required
def api_create_album():
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or request.form
        title = data.get("title", "")
        description = data.get("description", "")
        visibility = data.get("visibility", "public")
        album, error = create_album(profile["id"], title, description=description, visibility=visibility)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True, "album": album}), 201
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/albums/<album_id>/update", methods=["POST"])
@login_required
def api_update_album(album_id):
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or request.form
        updated, error = update_album(
            album_id,
            profile["id"],
            title=data.get("title"),
            description=data.get("description"),
            visibility=data.get("visibility"),
            cover_url=data.get("cover_url"),
        )
        if error:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True, "album": updated})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/albums/<album_id>", methods=["DELETE"])
@login_required
def api_delete_album(album_id):
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        ok, error = delete_album(album_id, profile["id"])
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/albums/<album_id>/add-media", methods=["POST"])
@login_required
def api_add_media_to_album(album_id):
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or request.form
        media_id = data.get("media_id")
        if not media_id:
            return jsonify({"ok": False, "error": "media_id is required"}), 400
        ok, error = add_media_to_album(album_id, media_id, profile["id"])
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/media/<media_id>/remove-from-album", methods=["POST"])
@login_required
def api_remove_media_from_album(media_id):
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        ok, error = remove_media_from_album(media_id, profile["id"])
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/media/<media_id>/visibility", methods=["POST"])
@login_required
def api_toggle_media_visibility(media_id):
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        data = request.get_json(silent=True) or request.form
        visibility = data.get("visibility", "public")
        updated, error = toggle_media_visibility(media_id, profile["id"], visibility)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True, "media": updated})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/media/<media_id>", methods=["DELETE"])
@login_required
def api_delete_media(media_id):
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        ok, error = delete_media(media_id, profile["id"])
        if not ok:
            return jsonify({"ok": False, "error": error}), 400
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/api/stats/<profile_id>")
@login_required
def api_media_stats(profile_id):
    try:
        stats = get_profile_media_stats(profile_id)
        return jsonify({"ok": True, "stats": stats})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@gallery_bp.route("/profile/<profile_id>")
@login_required
def gallery_page(profile_id):
    try:
        viewer = get_current_profile()
        if not viewer:
            return redirect("/auth/login")
        profile = get_profile_by_id(profile_id) or {}
        if not profile:
            return render_template("profile/not_found.html", username=""), 404
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
        album_id = request.args.get("album_id")
        media_items, total = get_profile_gallery(
            profile_id, viewer_id=viewer.get("id"),
            album_id=album_id, page=page, per_page=per_page,
        )
        albums = get_albums(profile_id, viewer_id=viewer.get("id"))
        stats = get_profile_media_stats(profile_id)
        total_pages = max(1, (total + per_page - 1) // per_page)
        is_following = bool(
            fast_query(
                "SELECT 1 FROM chain_follows WHERE follower_profile_id = %s AND following_profile_id = %s LIMIT 1",
                (viewer["id"], profile_id), default=[]
            )
        )
        sub_status = "inactive"
        try:
            sub_check = fast_query(
                "SELECT status FROM chain_subscriptions WHERE subscriber_id = %s AND creator_id = %s AND status = 'active' LIMIT 1",
                (viewer["id"], profile_id), default=[]
            )
            if sub_check:
                sub_status = sub_check[0].get("status", "inactive")
        except Exception:
            pass
        is_owner = str(viewer.get("id")) == str(profile_id)
        return render_template(
            "gallery/index.html",
            profile=profile, viewer=viewer,
            media_items=media_items, albums=albums, stats=stats,
            page=page, total_pages=total_pages, total=total,
            current_album_id=album_id,
            is_following=is_following,
            subscriber_status=sub_status,
        )
    except Exception as e:
        return f"Error loading gallery: {str(e)}", 500


@gallery_bp.route("/api/upload-media", methods=["POST"])
@login_required
def api_upload_media():
    try:
        profile = get_current_profile()
        if not profile:
            return jsonify({"ok": False, "error": "Unauthorized"}), 401
        file = request.files.get("file")
        if not file:
            return jsonify({"ok": False, "error": "No file provided"}), 400
        visibility = request.form.get("visibility", "public")
        album_id = request.form.get("album_id")
        from services.content_service import save_media_file
        result = save_media_file(file, upload_type="image", profile_id=profile["id"])
        if result:
            return jsonify({"ok": True, "media": result}), 201
        return jsonify({"ok": False, "error": "Upload failed"}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
