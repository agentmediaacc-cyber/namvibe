from flask import Blueprint, jsonify
from services.neon_service import fast_query

system_api_bp = Blueprint("system_api", __name__, url_prefix="/api/v1/system")

@system_api_bp.route("/version/<platform>")
def get_version(platform):
    """Returns the latest version and update requirements for a platform"""
    sql = "SELECT current_version, min_required_version, update_url FROM chain_api_versions WHERE platform = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 1"
    rows = fast_query(sql, (platform,))
    
    if not rows:
        # Fallback defaults
        return jsonify({
            "current_version": "1.0.0",
            "min_required_version": "1.0.0",
            "update_url": "https://chain.social/download"
        })
        
    return jsonify(rows[0])

@system_api_bp.route("/health")
def health_check():
    return jsonify({"status": "ok", "service": "chain_api", "version": "1.0.0"})
