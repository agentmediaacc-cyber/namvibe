from flask import Blueprint, jsonify
from services.neon_service import fast_query

config_bp = Blueprint("config", __name__, url_prefix="/api/config")

def _query(sql, params=None, default=None):
    rows = fast_query(sql, params or (), timeout_ms=5000, default=default or [])
    return rows

@config_bp.route("/live/categories")
def live_categories():
    rows = _query(
        "SELECT slug, label, icon, is_live, sort_order FROM chain_live_categories WHERE is_active = TRUE ORDER BY sort_order"
    )
    return jsonify({"categories": rows, "count": len(rows)})

@config_bp.route("/live/gift-tiers")
def gift_tiers():
    rows = _query(
        "SELECT slug, label, min_nvc, max_nvc, color, sort_order FROM chain_gift_tiers ORDER BY sort_order"
    )
    return jsonify({"tiers": rows, "count": len(rows)})

@config_bp.route("/live/gifts")
def live_gifts():
    rows = _query(
        "SELECT id, name, emoji, price_nvc, tier, is_premium, sort_order FROM chain_live_gift_catalog WHERE is_premium = FALSE ORDER BY sort_order"
    )
    premium = _query(
        "SELECT id, name, emoji, price_nvc, tier, is_premium, sort_order FROM chain_live_gift_catalog WHERE is_premium = TRUE ORDER BY sort_order"
    )
    return jsonify({"gifts": rows, "premium": premium, "count": len(rows) + len(premium)})

@config_bp.route("/live/types")
def live_types():
    rows = _query(
        "SELECT slug, label, sort_order FROM chain_live_types ORDER BY sort_order"
    )
    return jsonify({"types": rows, "count": len(rows)})

@config_bp.route("/live/room-types")
def room_types():
    rows = _query(
        "SELECT slug, label, sort_order FROM chain_room_types ORDER BY sort_order"
    )
    return jsonify({"types": rows, "count": len(rows)})

@config_bp.route("/interests")
def interests():
    rows = _query(
        "SELECT name, icon, category, sort_order FROM chain_interests ORDER BY sort_order"
    )
    return jsonify({"interests": rows, "count": len(rows)})

@config_bp.route("/languages")
def languages():
    rows = _query(
        "SELECT name, native_name, code FROM chain_languages ORDER BY sort_order"
    )
    return jsonify({"languages": rows, "count": len(rows)})

@config_bp.route("/creator-types")
def creator_types():
    rows = _query(
        "SELECT slug, label FROM chain_creator_types ORDER BY sort_order"
    )
    return jsonify({"types": rows, "count": len(rows)})

@config_bp.route("/notification-types")
def notification_types():
    rows = _query(
        "SELECT slug, label, icon, category FROM chain_notification_types ORDER BY category, slug"
    )
    return jsonify({"types": rows, "count": len(rows)})

@config_bp.route("/reactions")
def reactions():
    rows = _query(
        "SELECT emoji, label, sort_order FROM chain_reaction_types ORDER BY sort_order"
    )
    return jsonify({"reactions": rows, "count": len(rows)})

@config_bp.route("/all")
def all_config():
    return jsonify({
        "live_categories": _query("SELECT slug, label, icon, is_live FROM chain_live_categories WHERE is_active = TRUE ORDER BY sort_order"),
        "gift_tiers": _query("SELECT slug, label, min_nvc, max_nvc, color FROM chain_gift_tiers ORDER BY sort_order"),
        "gifts": _query("SELECT id, name, emoji, price_nvc, tier, is_premium FROM chain_live_gift_catalog ORDER BY sort_order"),
        "live_types": _query("SELECT slug, label FROM chain_live_types ORDER BY sort_order"),
        "room_types": _query("SELECT slug, label FROM chain_room_types ORDER BY sort_order"),
        "interests": _query("SELECT name, icon, category FROM chain_interests ORDER BY sort_order"),
        "languages": _query("SELECT name, native_name, code FROM chain_languages ORDER BY sort_order"),
        "creator_types": _query("SELECT slug, label FROM chain_creator_types ORDER BY sort_order"),
        "notification_types": _query("SELECT slug, label, icon, category FROM chain_notification_types ORDER BY category, slug"),
        "reactions": _query("SELECT emoji, label FROM chain_reaction_types ORDER BY sort_order"),
    })
