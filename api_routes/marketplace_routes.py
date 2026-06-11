from flask import Blueprint, flash, redirect, render_template, request, jsonify
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.marketplace_shop_service import (
    create_shop, get_shop, get_shop_by_profile, update_shop, list_shops, search_shops,
    create_product, get_product, list_products, search_products, save_product, unsave_product,
    list_saved_products,
    create_service, get_service, list_services, search_services,
    create_booking, get_booking, update_booking_status, list_bookings,
    create_review, list_reviews,
    get_seller_dashboard, marketplace_search, toggle_save,
)

marketplace_bp = Blueprint("marketplace", __name__)


# ─── HTML PAGES ──────────────────────────────────────────────

@marketplace_bp.route("/marketplace/")
def marketplace_home():
    try:
        from services.marketplace_service import list_public_items as _old_list
        items = _old_list()
    except Exception:
        items = []
    return render_template("marketplace/index.html", items=items)


@marketplace_bp.route("/marketplace/dashboard")
@login_required
def marketplace_dashboard():
    profile = get_current_profile()
    data = get_seller_dashboard(profile["id"])
    shop = data.get("shop")
    if not shop:
        shop = get_shop_by_profile(profile["id"])
    return render_template("marketplace/dashboard.html", profile=profile, data=data, shop=shop)


@marketplace_bp.route("/marketplace/create", methods=["GET", "POST"])
@login_required
def marketplace_create():
    from services.marketplace_service import create_marketplace_item
    from services.storage_service import upload_marketplace_media, upload_cover
    current = get_current_profile()
    if request.method == "POST":
        media_url = None
        media_upload_id = None
        cover_url = None
        cover_upload_id = None
        media_file = request.files.get("media")
        if media_file and media_file.filename:
            res, err = upload_marketplace_media(current["id"], media_file)
            if res:
                media_url = res["url"]
                media_upload_id = res["upload_id"]
                media_metadata = res
            else:
                flash(f"Media upload failed: {err}", "error")
        else:
            media_metadata = None
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(current["id"], cover_file)
            if res:
                cover_url = res["url"]
                cover_upload_id = res["upload_id"]
                cover_metadata = res
            else:
                flash(f"Cover upload failed: {err}", "error")
        else:
            cover_metadata = None
        create_marketplace_item(
            current["id"], request.form.get("item_type"), request.form.get("title"),
            request.form.get("description"), media_url, cover_url,
            request.form.get("price_coins"), request.form.get("premium_locked"),
            media_upload_id=media_upload_id, cover_upload_id=cover_upload_id,
            media_metadata=media_metadata, cover_metadata=cover_metadata,
        )
        flash("Marketplace item submitted for approval.", "success")
        return redirect("/marketplace/my-items")
    return render_template("marketplace/create.html", current=current)


# ─── API ─── SHOPS ───────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/shops", methods=["GET", "POST"])
def api_shops():
    if request.method == "GET":
        category = request.args.get("category")
        q = request.args.get("q")
        if q:
            data = search_shops(q)
        else:
            data = list_shops(category=category)
        return jsonify({"ok": True, "data": data})
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "login_required"}), 401
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    if not name:
        return jsonify({"ok": False, "error": "name_required"}), 400
    result = create_shop(profile["id"], name, body.get("shop_type", "personal"), **body)
    return jsonify(result), (200 if result.get("ok") else 400)


@marketplace_bp.route("/marketplace/api/shops/<shop_id>", methods=["GET", "PATCH"])
def api_shop_detail(shop_id):
    if request.method == "GET":
        shop = get_shop(shop_id)
        if not shop:
            return jsonify({"ok": False, "error": "not_found"}), 404
        return jsonify({"ok": True, "data": shop})
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "login_required"}), 401
    body = request.get_json(silent=True) or {}
    result = update_shop(shop_id, **body)
    return jsonify(result)


# ─── API ─── PRODUCTS ────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/products", methods=["GET", "POST"])
def api_products():
    if request.method == "GET":
        category = request.args.get("category")
        shop = request.args.get("shop_id")
        sort = request.args.get("sort", "newest")
        q = request.args.get("q")
        min_price = request.args.get("min_price", type=int)
        max_price = request.args.get("max_price", type=int)
        if q:
            data = search_products(q, category, min_price, max_price)
        else:
            data = list_products(category=category, shop_id=shop, sort=sort)
        return jsonify({"ok": True, "data": data})
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "login_required"}), 401
    body = request.get_json(silent=True) or {}
    shop_id = body.get("shop_id")
    title = body.get("title")
    price_cents = body.get("price_cents", 0)
    if not shop_id or not title:
        return jsonify({"ok": False, "error": "shop_id_and_title_required"}), 400
    result = create_product(profile["id"], shop_id, title, price_cents, **body)
    return jsonify(result), (200 if result.get("ok") else 400)


@marketplace_bp.route("/marketplace/api/products/<product_id>")
def api_product_detail(product_id):
    p = get_product(product_id)
    if not p:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "data": p})


@marketplace_bp.route("/marketplace/api/products/<product_id>/save", methods=["POST"])
@login_required
def api_save_product(product_id):
    profile = get_current_profile()
    result = save_product(profile["id"], product_id)
    return jsonify(result)


@marketplace_bp.route("/marketplace/api/products/<product_id>/unsave", methods=["POST"])
@login_required
def api_unsave_product(product_id):
    profile = get_current_profile()
    result = unsave_product(profile["id"], product_id)
    return jsonify(result)


# ─── API ─── SERVICES ────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/services", methods=["GET", "POST"])
def api_services():
    if request.method == "GET":
        category = request.args.get("category")
        shop = request.args.get("shop_id")
        q = request.args.get("q")
        if q:
            data = search_services(q, category)
        else:
            data = list_services(category=category, shop_id=shop)
        return jsonify({"ok": True, "data": data})
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "login_required"}), 401
    body = request.get_json(silent=True) or {}
    shop_id = body.get("shop_id")
    title = body.get("title")
    rate = body.get("hourly_rate_cents", 0)
    if not shop_id or not title:
        return jsonify({"ok": False, "error": "shop_id_and_title_required"}), 400
    result = create_service(profile["id"], shop_id, title, rate, **body)
    return jsonify(result), (200 if result.get("ok") else 400)


@marketplace_bp.route("/marketplace/api/services/<service_id>")
def api_service_detail(service_id):
    s = get_service(service_id)
    if not s:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "data": s})


# ─── API ─── BOOKINGS ────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/bookings", methods=["GET", "POST"])
@login_required
def api_bookings():
    profile = get_current_profile()
    if request.method == "GET":
        role = request.args.get("role", "client")
        status = request.args.get("status")
        data = list_bookings(profile["id"], role=role, status=status)
        return jsonify({"ok": True, "data": data})
    body = request.get_json(silent=True) or {}
    service_id = body.get("service_id")
    if not service_id:
        return jsonify({"ok": False, "error": "service_id_required"}), 400
    result = create_booking(profile["id"], service_id, **body)
    return jsonify(result), (200 if result.get("ok") else 400)


@marketplace_bp.route("/marketplace/api/bookings/<booking_id>/status", methods=["PATCH"])
@login_required
def api_booking_status(booking_id):
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if not status:
        return jsonify({"ok": False, "error": "status_required"}), 400
    booking = get_booking(booking_id)
    if not booking:
        return jsonify({"ok": False, "error": "not_found"}), 404
    if booking.get("provider_profile_id") != profile["id"] and booking.get("client_profile_id") != profile["id"]:
        return jsonify({"ok": False, "error": "not_authorized"}), 403
    result = update_booking_status(booking_id, status)
    return jsonify(result)


@marketplace_bp.route("/marketplace/api/bookings/<booking_id>")
@login_required
def api_booking_detail(booking_id):
    b = get_booking(booking_id)
    if not b:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "data": b})


# ─── API ─── REVIEWS ─────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/reviews", methods=["GET", "POST"])
def api_reviews():
    if request.method == "GET":
        target_type = request.args.get("target_type", "shop")
        target_id = request.args.get("target_id")
        if not target_id:
            return jsonify({"ok": False, "error": "target_id_required"}), 400
        data = list_reviews(target_type, target_id)
        return jsonify({"ok": True, "data": data})
    profile = get_current_profile()
    if not profile:
        return jsonify({"ok": False, "error": "login_required"}), 401
    body = request.get_json(silent=True) or {}
    body["reviewer_profile_id"] = profile["id"]
    result = create_review(profile["id"], **body)
    return jsonify(result), (200 if result.get("ok") else 400)


# ─── API ─── SEARCH ──────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/search")
def api_search():
    q = request.args.get("q", "")
    category = request.args.get("category")
    min_price = request.args.get("min_price", type=int)
    max_price = request.args.get("max_price", type=int)
    location = request.args.get("location")
    verified_only = request.args.get("verified_only", "false").lower() == "true"
    result = marketplace_search(q, category, min_price, max_price, location, verified_only)
    return jsonify({"ok": True, "data": result})


# ─── API ─── SAVED ───────────────────────────────────────────

@marketplace_bp.route("/marketplace/api/saved")
@login_required
def api_saved():
    profile = get_current_profile()
    data = list_saved_products(profile["id"])
    return jsonify({"ok": True, "data": data})


@marketplace_bp.route("/marketplace/api/saved/toggle", methods=["POST"])
@login_required
def api_toggle_save():
    profile = get_current_profile()
    body = request.get_json(silent=True) or {}
    item_type = body.get("item_type", "product")
    item_id = body.get("item_id")
    if not item_id:
        return jsonify({"ok": False, "error": "item_id_required"}), 400
    result = toggle_save(profile["id"], item_type, item_id)
    return jsonify(result)


# ─── API ─── SELLER DASHBOARD ────────────────────────────────

@marketplace_bp.route("/marketplace/api/dashboard")
@login_required
def api_dashboard():
    profile = get_current_profile()
    data = get_seller_dashboard(profile["id"])
    return jsonify({"ok": True, "data": data})


# ─── PRESERVE EXISTING ROUTES ────────────────────────────────

@marketplace_bp.route("/marketplace/my-items")
@login_required
def marketplace_my_items():
    from services.marketplace_service import list_my_items
    current = get_current_profile()
    return render_template("marketplace/my_items.html", current=current, items=list_my_items(current["id"]))


@marketplace_bp.route("/marketplace/item/<item_id>")
def marketplace_detail(item_id):
    from services.marketplace_service import get_item_access, get_item
    viewer = get_current_profile()
    access = get_item_access((viewer or {}).get("id"), item_id)
    item = access.get("item")
    if not item:
        return "Marketplace item not found", 404
    return render_template("marketplace/detail.html", item=item, access=access, viewer=viewer)


@marketplace_bp.route("/marketplace/purchase/<item_id>", methods=["POST"])
@login_required
def marketplace_purchase(item_id):
    from services.marketplace_service import purchase_item
    current = get_current_profile()
    ok, message = purchase_item(current["id"], item_id)
    flash("Purchase completed." if ok else message, "success" if ok else "error")
    return redirect(f"/marketplace/item/{item_id}")


@marketplace_bp.route("/marketplace/download/<purchase_id>")
@login_required
def marketplace_download(purchase_id):
    current = get_current_profile()
    from services.supabase_safe import safe_select
    rows = safe_select("chain_media_purchases", filters={"id": purchase_id}, limit=1, order_by=None)
    if not rows:
        return "This download is locked.", 404
    purchase = rows[0]
    if purchase.get("buyer_profile_id") != current.get("id"):
        return "This download is locked.", 403
    if purchase.get("purchase_status") != "completed" or not purchase.get("download_allowed", True):
        flash("This download is still locked.", "error")
        return redirect(f"/marketplace/item/{purchase.get('item_id')}")
    from services.marketplace_service import get_item
    item = get_item(purchase.get("item_id"))
    if not item or not item.get("download_enabled") or not item.get("download_url"):
        flash("This media is not ready for download yet.", "error")
        return redirect(f"/marketplace/item/{purchase.get('item_id')}")
    return redirect(item.get("download_url"))


@marketplace_bp.route("/music/albums/create", methods=["GET", "POST"])
@login_required
def music_album_create():
    from services.marketplace_service import create_album
    from services.storage_service import upload_cover
    current = get_current_profile()
    if request.method == "POST":
        cover_url = None
        cover_upload_id = None
        cover_file = request.files.get("cover")
        if cover_file and cover_file.filename:
            res, err = upload_cover(current["id"], cover_file)
            if res:
                cover_url = res["public_url"]
                cover_upload_id = res["upload_id"]
            else:
                flash(f"Album cover upload failed: {err}", "error")
        create_album(current["id"], request.form.get("title"), request.form.get("description"),
                     request.form.get("genre"), cover_url, request.form.get("price_coins"),
                     cover_upload_id=cover_upload_id)
        flash("Album submitted for approval.", "success")
        return redirect("/marketplace/my-items")
    return render_template("music/create_album.html", current=current)


@marketplace_bp.route("/music/tracks/upload", methods=["GET", "POST"])
@login_required
def music_track_upload():
    from services.marketplace_service import create_track
    from services.storage_service import upload_music_track
    current = get_current_profile()
    if request.method == "POST":
        audio_url = None
        audio_upload_id = None
        audio_file = request.files.get("audio")
        if audio_file and audio_file.filename:
            res, err = upload_music_track(current["id"], audio_file)
            if res:
                audio_url = res["public_url"]
                audio_upload_id = res["upload_id"]
            else:
                flash(f"Audio upload failed: {err}", "error")
        create_track(current["id"], request.form.get("album_id"), request.form.get("title"),
                     audio_url, request.form.get("price_coins"), audio_upload_id=audio_upload_id)
        flash("Track submitted for approval.", "success")
        return redirect("/marketplace/my-items")
    return render_template("music/upload_track.html", current=current)
