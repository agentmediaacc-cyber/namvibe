"""
NamVibe Advertising Platform — Admin Dashboard Routes.
Full control: campaigns, advertisers, payments, analytics,
moderation, fraud, coupons, promotions, AI review.
"""
from flask import Blueprint, jsonify, render_template, request
from services.admin_auth_service import require_admin, current_admin
from services.neon_service import fast_query
from services import advertising_service as ads

ad_admin_bp = Blueprint("ad_admin", __name__, url_prefix="/admin/ads")

# ── Dashboard Pages ──────────────────────────────────────────────────

@ad_admin_bp.route("/")
@require_admin
def dashboard():
    admin = current_admin()
    stats = ads.get_admin_dashboard_stats()
    campaigns = ads.get_campaigns_for_admin(limit=20)
    return render_template("admin/ads_dashboard.html", admin=admin, stats=stats, campaigns=campaigns)

@ad_admin_bp.route("/campaigns")
@require_admin
def campaigns_page():
    admin = current_admin()
    status = request.args.get("status")
    campaigns = ads.get_campaigns_for_admin(status=status, limit=100)
    return render_template("admin/ads_campaigns.html", admin=admin, campaigns=campaigns, status_filter=status)

@ad_admin_bp.route("/campaigns/<campaign_id>")
@require_admin
def campaign_detail(campaign_id):
    admin = current_admin()
    campaign = ads.get_campaign(campaign_id)
    if not campaign:
        return "Campaign not found", 404
    creatives = ads.get_creatives_for_campaign(campaign_id)
    placements = ads.get_campaign_placements(campaign_id)
    targeting = ads.get_campaign_targeting(campaign_id)
    stats = ads.get_campaign_stats(campaign_id)
    daily_stats = ads.get_campaign_daily_stats(campaign_id)
    return render_template("admin/ads_campaign_detail.html", admin=admin,
                           campaign=campaign, creatives=creatives,
                           placements=placements, targeting=targeting,
                           stats=stats, daily_stats=daily_stats)

@ad_admin_bp.route("/advertisers")
@require_admin
def advertisers_page():
    admin = current_admin()
    top = ads.get_top_advertisers(limit=50)
    return render_template("admin/ads_advertisers.html", admin=admin, advertisers=top)

@ad_admin_bp.route("/analytics")
@require_admin
def analytics_page():
    admin = current_admin()
    stats = ads.get_admin_dashboard_stats()
    top_ads = ads.get_top_performing_ads(20)
    return render_template("admin/ads_analytics.html", admin=admin, stats=stats, top_ads=top_ads)

@ad_admin_bp.route("/payments")
@require_admin
def payments_page():
    admin = current_admin()
    payments = ads.get_payments_for_admin(100)
    return render_template("admin/ads_payments.html", admin=admin, payments=payments)

@ad_admin_bp.route("/moderation")
@require_admin
def moderation_page():
    admin = current_admin()
    queue = ads.get_moderation_queue("pending", 50)
    reviewed = ads.get_all_moderation(50)
    return render_template("admin/ads_moderation.html", admin=admin, queue=queue, reviewed=reviewed)

@ad_admin_bp.route("/coupons")
@require_admin
def coupons_page():
    admin = current_admin()
    coupons = ads.get_coupons()
    return render_template("admin/ads_coupons.html", admin=admin, coupons=coupons)

@ad_admin_bp.route("/fraud")
@require_admin
def fraud_page():
    admin = current_admin()
    events = ads.get_fraud_events(limit=100)
    return render_template("admin/ads_fraud.html", admin=admin, events=events)

@ad_admin_bp.route("/reports")
@require_admin
def reports_page():
    admin = current_admin()
    stats = ads.get_admin_dashboard_stats()
    top_ads = ads.get_top_performing_ads(20)
    top_advertisers = ads.get_top_advertisers(10)
    return render_template("admin/ads_reports.html", admin=admin, stats=stats,
                           top_ads=top_ads, top_advertisers=top_advertisers)

# ── API: Campaigns ───────────────────────────────────────────────────

@ad_admin_bp.route("/api/campaigns")
@require_admin
def api_campaigns():
    status = request.args.get("status")
    campaigns = ads.get_campaigns_for_admin(status=status, limit=100)
    return jsonify({"ok": True, "campaigns": campaigns})

@ad_admin_bp.route("/api/campaigns/<campaign_id>")
@require_admin
def api_campaign(campaign_id):
    campaign = ads.get_campaign(campaign_id)
    if not campaign:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "campaign": campaign})

@ad_admin_bp.route("/api/campaigns/<campaign_id>/creatives")
@require_admin
def api_campaign_creatives(campaign_id):
    creatives = ads.get_creatives_for_campaign(campaign_id)
    return jsonify({"ok": True, "creatives": creatives})

@ad_admin_bp.route("/api/campaigns/<campaign_id>/stats")
@require_admin
def api_campaign_stats(campaign_id):
    stats = ads.get_campaign_stats(campaign_id)
    daily = ads.get_campaign_daily_stats(campaign_id)
    return jsonify({"ok": True, "stats": stats, "daily": daily})

# ── API: Approval Workflow ───────────────────────────────────────────

@ad_admin_bp.route("/api/approve", methods=["POST"])
@require_admin
def api_approve():
    admin = current_admin()
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    note = data.get("note")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.approve_campaign(campaign_id, admin_id=admin.get("id"), note=note)
    return jsonify(result)

@ad_admin_bp.route("/api/reject", methods=["POST"])
@require_admin
def api_reject():
    admin = current_admin()
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    note = data.get("note")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.reject_campaign(campaign_id, admin_id=admin.get("id"), note=note)
    return jsonify(result)

@ad_admin_bp.route("/api/pause", methods=["POST"])
@require_admin
def api_pause():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.pause_campaign(campaign_id)
    return jsonify(result)

@ad_admin_bp.route("/api/resume", methods=["POST"])
@require_admin
def api_resume():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.resume_campaign(campaign_id)
    return jsonify(result)

@ad_admin_bp.route("/api/duplicate", methods=["POST"])
@require_admin
def api_duplicate():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.duplicate_campaign(campaign_id)
    return jsonify(result)

@ad_admin_bp.route("/api/delete", methods=["POST"])
@require_admin
def api_delete():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.delete_campaign(campaign_id)
    return jsonify(result)

@ad_admin_bp.route("/api/schedule", methods=["POST"])
@require_admin
def api_schedule():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    start = data.get("start_date")
    end = data.get("end_date")
    if not campaign_id or not start:
        return jsonify({"ok": False, "error": "campaign_id and start_date required"}), 400
    result = ads.schedule_campaign(campaign_id, start, end)
    return jsonify(result)

# ── API: Edit Campaign ───────────────────────────────────────────────

@ad_admin_bp.route("/api/campaigns/<campaign_id>/update", methods=["POST"])
@require_admin
def api_update_campaign(campaign_id):
    data = request.get_json(silent=True) or request.form
    allowed = {"title","objective","ad_type","target_url","budget","daily_budget",
               "category","bid_type","bid_amount","content_url"}
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    result = ads.update_campaign(campaign_id, **updates)
    return jsonify(result)

@ad_admin_bp.route("/api/campaigns/<campaign_id>/creatives/add", methods=["POST"])
@require_admin
def api_add_creative(campaign_id):
    data = request.get_json(silent=True) or request.form
    campaign = ads.get_campaign(campaign_id)
    if not campaign:
        return jsonify({"ok": False, "error": "Campaign not found"}), 404
    result = ads.create_creative(
        campaign_id=campaign_id,
        profile_id=campaign["owner_id"],
        creative_type=data.get("creative_type", "image"),
        media_url=data.get("media_url"),
        headline=data.get("headline"),
        description=data.get("description"),
        cta_text=data.get("cta_text", "Learn More"),
        destination_url=data.get("destination_url"),
    )
    return jsonify(result)

@ad_admin_bp.route("/api/campaigns/<campaign_id>/placements", methods=["POST"])
@require_admin
def api_set_placements(campaign_id):
    data = request.get_json(silent=True) or request.form
    types = data.get("placement_types", [])
    if isinstance(types, str):
        types = [t.strip() for t in types.split(",")]
    result = ads.set_campaign_placements(campaign_id, types)
    return jsonify(result)

@ad_admin_bp.route("/api/campaigns/<campaign_id>/targeting", methods=["POST"])
@require_admin
def api_set_targeting(campaign_id):
    data = request.get_json(silent=True) or request.form
    result = ads.set_campaign_targeting(campaign_id, data)
    return jsonify(result)

# ── API: AI Review ───────────────────────────────────────────────────

@ad_admin_bp.route("/api/ai-review", methods=["POST"])
@require_admin
def api_ai_review():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required"}), 400
    result = ads.run_ai_review(campaign_id)
    return jsonify(result)

@ad_admin_bp.route("/api/ai-review/all", methods=["POST"])
@require_admin
def api_ai_review_all():
    pending = ads.get_campaigns_for_admin(status="pending", limit=50)
    results = []
    for c in pending:
        r = ads.run_ai_review(c["id"])
        results.append({"campaign_id": c["id"], "title": c.get("title"), "result": r})
    return jsonify({"ok": True, "results": results})

# ── API: Moderation ──────────────────────────────────────────────────

@ad_admin_bp.route("/api/moderation/review", methods=["POST"])
@require_admin
def api_moderation_review():
    admin = current_admin()
    data = request.get_json(silent=True) or request.form
    mod_id = data.get("moderation_id")
    review_status = data.get("review_status")
    notes = data.get("notes")
    if not mod_id or not review_status:
        return jsonify({"ok": False, "error": "moderation_id and review_status required"}), 400
    result = ads.review_moderation(mod_id, review_status, admin.get("id"), notes)
    if review_status == "approved":
        rows = fast_query("SELECT campaign_id FROM chain_ad_moderation WHERE id = %s", (mod_id,), default=[])
        if rows:
            ads.approve_campaign(rows[0]["campaign_id"], admin.get("id"), notes)
    elif review_status == "rejected":
        rows = fast_query("SELECT campaign_id FROM chain_ad_moderation WHERE id = %s", (mod_id,), default=[])
        if rows:
            ads.reject_campaign(rows[0]["campaign_id"], admin.get("id"), notes)
    return jsonify(result)

# ── API: Coupons ─────────────────────────────────────────────────────

@ad_admin_bp.route("/api/coupons/create", methods=["POST"])
@require_admin
def api_create_coupon():
    data = request.get_json(silent=True) or request.form
    result = ads.create_coupon(
        code=data.get("code"),
        discount_type=data.get("discount_type"),
        discount_value=data.get("discount_value"),
        description=data.get("description"),
        min_spend=data.get("min_spend", 0),
        max_discount=data.get("max_discount"),
        usage_limit=data.get("usage_limit", 1),
        expires_at=data.get("expires_at"),
    )
    return jsonify(result)

# ── API: Promotions ──────────────────────────────────────────────────

@ad_admin_bp.route("/api/promotions/create", methods=["POST"])
@require_admin
def api_create_promotion():
    data = request.get_json(silent=True) or request.form
    result = ads.create_promotion(
        campaign_id=data.get("campaign_id"),
        content_type=data.get("content_type"),
        content_id=data.get("content_id"),
        profile_id=data.get("profile_id"),
    )
    return jsonify(result)

# ── API: Dashboard Stats ─────────────────────────────────────────────

@ad_admin_bp.route("/api/dashboard")
@require_admin
def api_dashboard():
    stats = ads.get_admin_dashboard_stats()
    top_ads = ads.get_top_performing_ads(5)
    top_advertisers = ads.get_top_advertisers(5)
    return jsonify({
        "ok": True,
        "stats": stats,
        "top_ads": top_ads,
        "top_advertisers": top_advertisers,
    })
