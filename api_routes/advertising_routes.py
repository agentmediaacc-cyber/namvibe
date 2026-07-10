"""
NamVibe Advertising Platform — Advertiser Portal Routes.
Users can manage campaigns, creatives, view analytics, and handle billing.
"""
from flask import Blueprint, jsonify, render_template, request, session
from functools import wraps
from services.neon_service import fast_query

advertising_bp = Blueprint("advertising", __name__, url_prefix="/advertising")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        profile_id = session.get("profile_id")
        if not profile_id:
            return jsonify({"ok": False, "error": "Login required"}), 401
        return f(profile_id, *args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def _get_profile_id():
    return session.get("profile_id")

def _parse_amount(value, default=0.0):
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return None

def _get_owned_campaign_or_404(profile_id, campaign_id):
    from services import advertising_service as ads
    campaign = ads.get_campaign(campaign_id)
    if not campaign or campaign.get("owner_id") != profile_id:
        return None
    return campaign

# ── Pages ────────────────────────────────────────────────────────────

@advertising_bp.route("/")
def portal():
    profile_id = _get_profile_id()
    if not profile_id:
        return render_template("auth/login.html", next_path="/advertising/")
    from services import advertising_service as ads
    campaigns = ads.get_campaigns_for_user(profile_id)
    stats = ads.get_advertiser_stats(profile_id)
    advertiser = ads.get_or_create_advertiser(profile_id)
    return render_template("advertising/portal.html",
                           campaigns=campaigns, stats=stats, advertiser=advertiser)

@advertising_bp.route("/create")
def create_page():
    profile_id = _get_profile_id()
    if not profile_id:
        return render_template("auth/login.html", next_path="/advertising/create")
    return render_template("advertising/create_campaign.html")

@advertising_bp.route("/campaigns/<campaign_id>")
def campaign_page(campaign_id):
    profile_id = _get_profile_id()
    if not profile_id:
        return render_template("auth/login.html")
    from services import advertising_service as ads
    campaign = ads.get_campaign(campaign_id)
    if not campaign or campaign["owner_id"] != profile_id:
        return "Campaign not found", 404
    creatives = ads.get_creatives_for_campaign(campaign_id)
    placements = ads.get_campaign_placements(campaign_id)
    targeting = ads.get_campaign_targeting(campaign_id)
    stats = ads.get_campaign_stats(campaign_id)
    daily = ads.get_campaign_daily_stats(campaign_id)
    return render_template("advertising/campaign_detail.html",
                           campaign=campaign, creatives=creatives,
                           placements=placements, targeting=targeting,
                           stats=stats, daily=daily)

# ── API: Advertiser Profile ──────────────────────────────────────────

@advertising_bp.route("/api/advertiser")
@login_required
def api_advertiser(profile_id):
    from services import advertising_service as ads
    advertiser = ads.get_or_create_advertiser(profile_id)
    return jsonify({"ok": True, "advertiser": advertiser})

@advertising_bp.route("/api/advertiser/update", methods=["POST"])
@login_required
def api_update_advertiser(profile_id):
    from services import advertising_service as ads
    data = request.get_json(silent=True) or request.form
    result = ads.update_advertiser(profile_id, **data)
    return jsonify(result)

# ── API: Campaigns ───────────────────────────────────────────────────

@advertising_bp.route("/api/campaigns")
@login_required
def api_campaigns(profile_id):
    from services import advertising_service as ads
    campaigns = ads.get_campaigns_for_user(profile_id)
    return jsonify({"ok": True, "campaigns": campaigns})

@advertising_bp.route("/api/campaigns/create", methods=["POST"])
@login_required
def api_create_campaign(profile_id):
    from services import advertising_service as ads
    data = request.get_json(silent=True) or request.form
    budget = _parse_amount(data.get("budget", 0))
    daily_budget = _parse_amount(data.get("daily_budget", 0))
    bid_amount = _parse_amount(data.get("bid_amount", 0))
    if budget is None or daily_budget is None or bid_amount is None:
        return jsonify({"ok": False, "error": "Invalid numeric campaign values"}), 400
    if budget < 0 or daily_budget < 0 or bid_amount < 0:
        return jsonify({"ok": False, "error": "Campaign amounts must be non-negative"}), 400
    if daily_budget and budget and daily_budget > budget:
        return jsonify({"ok": False, "error": "Daily budget cannot exceed total budget"}), 400
    result = ads.create_campaign(
        profile_id=profile_id,
        title=data.get("title") or data.get("name", "Untitled Campaign"),
        objective=data.get("objective", "reach"),
        ad_type=data.get("ad_type", "feed"),
        media_url=data.get("media_url") or data.get("content_url"),
        target_url=data.get("target_url"),
        budget=budget,
        daily_budget=daily_budget,
        start_date=data.get("start_date"),
        end_date=data.get("end_date"),
        media_type=data.get("media_type", "image"),
        category=data.get("category"),
        bid_type=data.get("bid_type", "auto"),
        bid_amount=bid_amount,
        currency=data.get("currency", "NAD"),
    )
    if result.get("ok"):
        ads.get_or_create_advertiser(profile_id)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/update", methods=["POST"])
@login_required
def api_update_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    data = request.get_json(silent=True) or request.form
    result = ads.update_campaign(campaign_id, profile_id=profile_id, **data)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/pause", methods=["POST"])
@login_required
def api_pause_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    result = ads.pause_campaign(campaign_id, profile_id)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/resume", methods=["POST"])
@login_required
def api_resume_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    campaign = ads.get_campaign(campaign_id)
    if not campaign or campaign["owner_id"] != profile_id:
        return jsonify({"ok": False, "error": "Not found"}), 404
    result = ads.resume_campaign(campaign_id)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/delete", methods=["POST"])
@login_required
def api_delete_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    result = ads.delete_campaign(campaign_id, profile_id)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/duplicate", methods=["POST"])
@login_required
def api_duplicate_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    result = ads.duplicate_campaign(campaign_id, profile_id)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/submit", methods=["POST"])
@login_required
def api_submit_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    campaign = ads.get_campaign(campaign_id)
    if not campaign or campaign["owner_id"] != profile_id:
        return jsonify({"ok": False, "error": "Not found"}), 404
    result = ads.submit_for_review(campaign_id)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/fund", methods=["POST"])
@login_required
def api_fund_campaign(profile_id, campaign_id):
    from services import advertising_service as ads
    campaign = ads.get_campaign(campaign_id)
    if not campaign:
        return jsonify({"ok": False, "error": "campaign_not_found"}), 404
    if campaign.get("owner_id") != profile_id:
        return jsonify({"ok": False, "error": "forbidden"}), 403
    data = request.get_json(silent=True) or request.form
    idempotency_key = data.get("idempotency_key") if data else None
    result = ads.fund_campaign(campaign_id, profile_id, idempotency_key=idempotency_key)
    status_code = 200
    if result.get("error") == "campaign_not_found":
        status_code = 404
    elif result.get("error") == "forbidden":
        status_code = 403
    elif result.get("error") in {"invalid_state", "already_funded"}:
        status_code = 409
    elif result.get("error") == "insufficient_funds":
        status_code = 402
    elif result.get("error") == "payment_failed":
        status_code = 400
    return jsonify(result), status_code

# ── API: Creatives ───────────────────────────────────────────────────

@advertising_bp.route("/api/campaigns/<campaign_id>/creatives")
@login_required
def api_creatives(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    creatives = ads.get_creatives_for_campaign(campaign_id)
    return jsonify({"ok": True, "creatives": creatives})

@advertising_bp.route("/api/campaigns/<campaign_id>/creatives/add", methods=["POST"])
@login_required
def api_add_creative(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    data = request.get_json(silent=True) or request.form
    result = ads.create_creative(
        campaign_id=campaign_id,
        profile_id=profile_id,
        creative_type=data.get("creative_type", "image"),
        media_url=data.get("media_url"),
        headline=data.get("headline"),
        description=data.get("description"),
        cta_text=data.get("cta_text", "Learn More"),
        destination_url=data.get("destination_url"),
        thumbnail_url=data.get("thumbnail_url"),
    )
    return jsonify(result)

@advertising_bp.route("/api/creatives/<creative_id>/delete", methods=["POST"])
@login_required
def api_delete_creative(profile_id, creative_id):
    from services import advertising_service as ads
    result = ads.delete_creative(creative_id, profile_id=profile_id)
    return jsonify(result)

# ── API: Placements & Targeting ──────────────────────────────────────

@advertising_bp.route("/api/campaigns/<campaign_id>/placements", methods=["POST"])
@login_required
def api_set_placements(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    data = request.get_json(silent=True) or request.form
    types = data.get("placement_types", [])
    if isinstance(types, str):
        types = [t.strip() for t in types.split(",")]
    result = ads.set_campaign_placements(campaign_id, types)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/targeting", methods=["POST"])
@login_required
def api_set_targeting(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    data = request.get_json(silent=True) or request.form
    result = ads.set_campaign_targeting(campaign_id, data)
    return jsonify(result)

@advertising_bp.route("/api/campaigns/<campaign_id>/targeting")
@login_required
def api_get_targeting(profile_id, campaign_id):
    from services import advertising_service as ads
    if not _get_owned_campaign_or_404(profile_id, campaign_id):
        return jsonify({"ok": False, "error": "Not found"}), 404
    targeting = ads.get_campaign_targeting(campaign_id)
    return jsonify({"ok": True, "targeting": targeting})

# ── API: Analytics ───────────────────────────────────────────────────

@advertising_bp.route("/api/stats")
@login_required
def api_stats(profile_id):
    from services import advertising_service as ads
    stats = ads.get_advertiser_stats(profile_id)
    return jsonify({"ok": True, "stats": stats})

@advertising_bp.route("/api/campaigns/<campaign_id>/stats")
@login_required
def api_campaign_stats(profile_id, campaign_id):
    from services import advertising_service as ads
    campaign = ads.get_campaign(campaign_id)
    if not campaign or campaign["owner_id"] != profile_id:
        return jsonify({"ok": False, "error": "Not found"}), 404
    stats = ads.get_campaign_stats(campaign_id)
    daily = ads.get_campaign_daily_stats(campaign_id)
    return jsonify({"ok": True, "stats": stats, "daily": daily})

# ── API: Payments ────────────────────────────────────────────────────

@advertising_bp.route("/api/payments")
@login_required
def api_payments(profile_id):
    from services import advertising_service as ads
    payments = ads.get_payments_for_profile(profile_id)
    return jsonify({"ok": True, "payments": payments})

# ── Ad Serving API (public) ──────────────────────────────────────────

@advertising_bp.route("/api/serve/<placement_type>")
def api_serve_ads(placement_type):
    viewer_id = _get_profile_id()
    slot_count = request.args.get("count", 2, type=int)
    from services import advertising_service as ads
    ads_list = ads.get_ads_for_placement(placement_type, viewer_id, slot_count)
    return jsonify({"ok": True, "ads": ads_list, "placement": placement_type})

@advertising_bp.route("/api/serve/feed")
def api_serve_feed():
    viewer_id = _get_profile_id()
    count = request.args.get("count", 2, type=int)
    from services import advertising_service as ads
    return jsonify({"ok": True, "ads": ads.get_ads_for_feed(viewer_id, count)})

@advertising_bp.route("/api/serve/reels")
def api_serve_reels():
    viewer_id = _get_profile_id()
    count = request.args.get("count", 1, type=int)
    from services import advertising_service as ads
    return jsonify({"ok": True, "ads": ads.get_ads_for_reels(viewer_id, count)})

@advertising_bp.route("/api/serve/stories")
def api_serve_stories():
    viewer_id = _get_profile_id()
    count = request.args.get("count", 1, type=int)
    from services import advertising_service as ads
    return jsonify({"ok": True, "ads": ads.get_ads_for_stories(viewer_id, count)})

@advertising_bp.route("/api/serve/search")
def api_serve_search():
    viewer_id = _get_profile_id()
    count = request.args.get("count", 2, type=int)
    from services import advertising_service as ads
    return jsonify({"ok": True, "ads": ads.get_ads_for_search(viewer_id, count)})

@advertising_bp.route("/api/serve/marketplace")
def api_serve_marketplace():
    viewer_id = _get_profile_id()
    count = request.args.get("count", 2, type=int)
    from services import advertising_service as ads
    return jsonify({"ok": True, "ads": ads.get_ads_for_marketplace(viewer_id, count)})

# ── Track: Impressions & Clicks ──────────────────────────────────────

@advertising_bp.route("/api/track/impression", methods=["POST"])
def api_track_impression():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    profile_id = _get_profile_id()
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    from services import advertising_service as ads
    if not ads.record_impression(campaign_id, profile_id):
        return jsonify({"ok": False, "error": "impression_record_failed"}), 400
    return jsonify({"ok": True})

@advertising_bp.route("/api/track/click", methods=["POST"])
def api_track_click():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    profile_id = _get_profile_id()
    ip = request.remote_addr
    ua = request.headers.get("User-Agent")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    from services import advertising_service as ads
    result = ads.track_click(campaign_id, profile_id, ip, ua)
    if not result.get("ok") and result.get("is_fraud"):
        return jsonify({"ok": False, "error": "Click blocked by fraud detection"}), 429
    if not result.get("ok"):
        return jsonify({"ok": False, "error": result.get("error", "click_record_failed")}), 500
    return jsonify({"ok": True})

# ── API: Coupon Validation ───────────────────────────────────────────

@advertising_bp.route("/api/coupon/validate", methods=["POST"])
def api_validate_coupon():
    data = request.get_json(silent=True) or request.form
    code = data.get("code")
    amount = _parse_amount(data.get("amount", 0))
    profile_id = _get_profile_id()
    if not code:
        return jsonify({"ok": False, "error": "Code required"}), 400
    if amount is None:
        return jsonify({"ok": False, "error": "Invalid amount"}), 400
    from services import advertising_service as ads
    if amount > 0:
        result = ads.apply_coupon(code, amount)
    else:
        result = ads.validate_coupon(code, profile_id)
    return jsonify(result)
