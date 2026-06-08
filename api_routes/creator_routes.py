from flask import Blueprint, render_template, g, jsonify, request
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.creator_analytics_engine import get_creator_stats
from services.creator_feature_service import (
    creator_dashboard,
    request_verification,
    create_subscription,
    create_paid_post,
    create_premium_content,
    request_payout,
    record_gift_conversion,
    create_revenue_report,
    create_sponsorship,
    award_creator_badge,
    award_supporter_badge,
    upsert_top_fan,
    upsert_creator_ranking,
)

creator_bp = Blueprint('creator', __name__, url_prefix='/creator')

@creator_bp.route('/dashboard')
@login_required
def dashboard():
    profile = get_current_profile()
    stats = {**creator_dashboard(profile["id"]), **get_creator_stats(profile['id'])}
    return render_template('creator/dashboard.html', stats=stats, profile=profile)


@creator_bp.route('/verification/request', methods=['POST'])
@login_required
def verification_request():
    profile = get_current_profile()
    result = request_verification(profile["id"])
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/subscriptions', methods=['POST'])
@login_required
def api_subscription():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = create_subscription(profile["id"], data.get("subscriber_profile_id") or profile["id"], data.get("tier", "standard"), data.get("price_coins", 0), data.get("status", "active"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/paid-posts', methods=['POST'])
@login_required
def api_paid_post():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = create_paid_post(profile["id"], data.get("title") or "Paid post", data.get("price_coins", 0), data.get("post_id"), data.get("status", "active"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/premium-content', methods=['POST'])
@login_required
def api_premium_content():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = create_premium_content(profile["id"], data.get("content_type", "post"), data.get("content_id"), data.get("lock_type", "subscription"), data.get("price_coins", 0))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/payouts', methods=['POST'])
@login_required
def api_payout():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = request_payout(profile["id"], data.get("amount_coins", 0), data.get("payout_method"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/gift-conversions', methods=['POST'])
@login_required
def api_gift_conversion():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = record_gift_conversion(profile["id"], data.get("supporter_profile_id"), data.get("gift_id"), data.get("coins", 0), data.get("conversion_rate", 1))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/revenue-reports', methods=['POST'])
@login_required
def api_revenue_report():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = create_revenue_report(profile["id"], data.get("period_key") or "current", data.get("gross_coins", 0), data.get("net_coins", 0), **(data.get("payload") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/sponsorships', methods=['POST'])
@login_required
def api_sponsorship():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = create_sponsorship(profile["id"], data.get("sponsor_name") or "Sponsor", data.get("amount_coins", 0), data.get("status", "prospect"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/badges', methods=['POST'])
@login_required
def api_creator_badge():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = award_creator_badge(profile["id"], data.get("badge_key") or "creator", data.get("label"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/supporter-badges', methods=['POST'])
@login_required
def api_supporter_badge():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = award_supporter_badge(profile["id"], data.get("supporter_profile_id") or profile["id"], data.get("badge_key") or "supporter", data.get("label"), **(data.get("metadata") or {}))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/top-fans', methods=['POST'])
@login_required
def api_top_fan():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = upsert_top_fan(profile["id"], data.get("fan_profile_id") or profile["id"], data.get("score", 0), data.get("rank"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200


@creator_bp.route('/rankings', methods=['POST'])
@login_required
def api_ranking():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    result = upsert_creator_ranking(profile["id"], data.get("category", "overall"), data.get("score", 0), data.get("rank"))
    return jsonify({"success": bool(result.get("ok")), **result}), 200
