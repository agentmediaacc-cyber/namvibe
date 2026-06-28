"""Admin advertising campaign management."""
from flask import Blueprint, jsonify, render_template, request
from services.admin_auth_service import require_admin, current_admin
from services.business_page_service import get_all_campaigns, approve_campaign, reject_campaign

ad_admin_bp = Blueprint("ad_admin", __name__, url_prefix="/admin/ads")

@ad_admin_bp.route("/")
@require_admin
def dashboard():
    admin = current_admin()
    campaigns = get_all_campaigns(50)
    return render_template("admin/ads.html", admin=admin, campaigns=campaigns)

@ad_admin_bp.route("/api/campaigns")
@require_admin
def api_campaigns():
    campaigns = get_all_campaigns(50)
    return jsonify({"ok": True, "campaigns": campaigns})

@ad_admin_bp.route("/api/approve", methods=["POST"])
@require_admin
def api_approve():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required."}), 400
    result = approve_campaign(campaign_id)
    return jsonify(result)

@ad_admin_bp.route("/api/reject", methods=["POST"])
@require_admin
def api_reject():
    data = request.get_json(silent=True) or request.form
    campaign_id = data.get("campaign_id")
    if not campaign_id:
        return jsonify({"ok": False, "error": "campaign_id required."}), 400
    result = reject_campaign(campaign_id)
    return jsonify(result)
