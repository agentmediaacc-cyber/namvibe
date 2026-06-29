import time
from flask import Blueprint, jsonify, render_template, request
from services.profile_service import get_current_profile
from api_routes.profile_routes import login_required
from services.creator_studio_service import (
    get_studio_dashboard,
    get_studio_analytics,
    get_studio_earnings,
    get_earnings_by_type,
    get_transaction_history,
    check_duplicate_payout,
    get_drafts, create_draft, update_draft, delete_draft,
    get_scheduled_posts, create_scheduled_post, cancel_scheduled_post,
    archive_content, restore_content, get_archived_content,
    get_keyword_filters, add_keyword_filter, remove_keyword_filter,
    get_hidden_words, add_hidden_word, remove_hidden_word,
    get_review_queue, approve_review_item, reject_review_item,
    get_link_hub, add_link_hub, remove_link_hub,
    get_contact_info, set_contact_info,
    get_business_hours, set_business_hours, update_business_profile,
    get_milestones, check_and_notify_milestones, get_or_create_weekly_summary,
)

studio_bp = Blueprint("creator_studio", __name__, url_prefix="/creator-studio")


@studio_bp.route("/")
@login_required
def studio_dashboard():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return "Not authenticated", 401
    return render_template("creator/studio_dashboard.html", profile=profile)


# ─── Dashboard API ───

@studio_bp.route("/api/dashboard")
@login_required
def api_dashboard():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_studio_dashboard(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/analytics")
@login_required
def api_analytics():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    period = request.args.get("period", "weekly")
    days = int(request.args.get("days", 30))
    resp = get_studio_analytics(profile["id"], period=period, days=days)
    return jsonify(resp)


# ─── Earnings API ───

@studio_bp.route("/api/earnings")
@login_required
def api_earnings():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_studio_earnings(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/earnings/by-type")
@login_required
def api_earnings_by_type():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    days = int(request.args.get("days", 90))
    resp = get_earnings_by_type(profile["id"], days=days)
    return jsonify(resp)


@studio_bp.route("/api/transactions")
@login_required
def api_transactions():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    limit = int(request.args.get("limit", 50))
    offset = int(request.args.get("offset", 0))
    resp = get_transaction_history(profile["id"], limit=limit, offset=offset)
    return jsonify(resp)


@studio_bp.route("/api/payout/check-duplicate", methods=["POST"])
@login_required
def api_payout_check_duplicate():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    amount = int(data.get("amount_cents", 0))
    ref_id = data.get("reference_id")
    resp = check_duplicate_payout(profile["id"], amount, ref_id)
    return jsonify(resp)


# ─── Content Management ───

@studio_bp.route("/api/drafts", methods=["GET"])
@login_required
def api_drafts_list():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    ct = request.args.get("content_type")
    resp = get_drafts(profile["id"], content_type=ct)
    return jsonify(resp)


@studio_bp.route("/api/drafts", methods=["POST"])
@login_required
def api_drafts_create():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = create_draft(profile["id"], data.get("content_type"), data.get("title"), data.get("body"), data.get("media_url"), data.get("metadata"))
    return jsonify(resp)


@studio_bp.route("/api/drafts/<draft_id>", methods=["PUT", "PATCH"])
@login_required
def api_drafts_update(draft_id):
    data = request.get_json(silent=True) or {}
    resp = update_draft(draft_id, data.get("title"), data.get("body"), data.get("media_url"), data.get("metadata"))
    return jsonify(resp)


@studio_bp.route("/api/drafts/<draft_id>", methods=["DELETE"])
@login_required
def api_drafts_delete(draft_id):
    resp = delete_draft(draft_id)
    return jsonify(resp)


@studio_bp.route("/api/scheduled", methods=["GET"])
@login_required
def api_scheduled_list():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    status = request.args.get("status")
    resp = get_scheduled_posts(profile["id"], status=status)
    return jsonify(resp)


@studio_bp.route("/api/scheduled", methods=["POST"])
@login_required
def api_scheduled_create():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = create_scheduled_post(profile["id"], data.get("scheduled_at"), data.get("content_type"), data.get("title"), data.get("body"), data.get("media_url"), data.get("metadata"))
    return jsonify(resp)


@studio_bp.route("/api/scheduled/<post_id>/cancel", methods=["POST"])
@login_required
def api_scheduled_cancel(post_id):
    resp = cancel_scheduled_post(post_id)
    return jsonify(resp)


# ─── Archive ───

@studio_bp.route("/api/archive", methods=["POST"])
@login_required
def api_archive():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = archive_content(profile["id"], data.get("entity_type"), data.get("entity_id"))
    return jsonify(resp)


@studio_bp.route("/api/archive/restore", methods=["POST"])
@login_required
def api_restore():
    data = request.get_json(silent=True) or {}
    resp = restore_content(data.get("entity_type"), data.get("entity_id"))
    return jsonify(resp)


@studio_bp.route("/api/archived")
@login_required
def api_archived():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_archived_content(profile["id"])
    return jsonify(resp)


# ─── Moderation ───

@studio_bp.route("/api/moderation/keywords", methods=["GET"])
@login_required
def api_keywords_list():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_keyword_filters(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/moderation/keywords", methods=["POST"])
@login_required
def api_keywords_add():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = add_keyword_filter(profile["id"], data.get("keyword"), data.get("action", "hide"))
    return jsonify(resp)


@studio_bp.route("/api/moderation/keywords/<filter_id>", methods=["DELETE"])
@login_required
def api_keywords_remove(filter_id):
    resp = remove_keyword_filter(filter_id)
    return jsonify(resp)


@studio_bp.route("/api/moderation/hidden-words", methods=["GET"])
@login_required
def api_hidden_words_list():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_hidden_words(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/moderation/hidden-words", methods=["POST"])
@login_required
def api_hidden_words_add():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = add_hidden_word(profile["id"], data.get("word"))
    return jsonify(resp)


@studio_bp.route("/api/moderation/hidden-words", methods=["DELETE"])
@login_required
def api_hidden_words_remove():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or request.args
    resp = remove_hidden_word(profile["id"], data.get("word"))
    return jsonify(resp)


@studio_bp.route("/api/moderation/review-queue")
@login_required
def api_review_queue():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    status = request.args.get("status", "pending")
    resp = get_review_queue(profile["id"], status=status)
    return jsonify(resp)


@studio_bp.route("/api/moderation/review-queue/<item_id>/approve", methods=["POST"])
@login_required
def api_review_approve(item_id):
    resp = approve_review_item(item_id)
    return jsonify(resp)


@studio_bp.route("/api/moderation/review-queue/<item_id>/reject", methods=["POST"])
@login_required
def api_review_reject(item_id):
    resp = reject_review_item(item_id)
    return jsonify(resp)


# ─── Business Tools ───

@studio_bp.route("/api/business/links", methods=["GET"])
@login_required
def api_links_list():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_link_hub(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/business/links", methods=["POST"])
@login_required
def api_links_add():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = add_link_hub(profile["id"], data.get("title"), data.get("url"), data.get("sort_order", 0))
    return jsonify(resp)


@studio_bp.route("/api/business/links/<link_id>", methods=["DELETE"])
@login_required
def api_links_remove(link_id):
    resp = remove_link_hub(link_id)
    return jsonify(resp)


@studio_bp.route("/api/business/contact", methods=["GET"])
@login_required
def api_contact_get():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_contact_info(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/business/contact", methods=["POST"])
@login_required
def api_contact_set():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = set_contact_info(profile["id"], data.get("contact_type"), data.get("contact_value"), data.get("is_public", False))
    return jsonify(resp)


@studio_bp.route("/api/business/hours", methods=["GET"])
@login_required
def api_hours_get():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_business_hours(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/business/hours", methods=["POST"])
@login_required
def api_hours_set():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = set_business_hours(profile["id"], data.get("day_of_week"), data.get("open_time"), data.get("close_time"), data.get("is_closed", False))
    return jsonify(resp)


@studio_bp.route("/api/business/profile", methods=["POST"])
@login_required
def api_business_profile():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    resp = update_business_profile(profile["id"], data.get("business_category"), data.get("contact_button_label"), data.get("contact_button_url"))
    return jsonify(resp)


# ─── Milestones ───

@studio_bp.route("/api/milestones")
@login_required
def api_milestones():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_milestones(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/milestones/check", methods=["POST"])
@login_required
def api_milestones_check():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = check_and_notify_milestones(profile["id"])
    return jsonify(resp)


@studio_bp.route("/api/weekly-summary", methods=["GET", "POST"])
@login_required
def api_weekly_summary():
    profile = get_current_profile()
    if not profile or not profile.get("id"):
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    resp = get_or_create_weekly_summary(profile["id"])
    return jsonify(resp)
