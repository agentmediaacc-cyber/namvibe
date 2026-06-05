from flask import Blueprint, jsonify, request, render_template
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile
from services.neon_service import fast_query, write_query

admin_safety_bp = Blueprint('admin_safety', __name__, url_prefix='/admin/safety')

@admin_safety_bp.route('/')
@login_required
def dashboard():
    profile = get_current_profile()
    # In a real app, check for is_admin flag
    # For now, let's just allow access
    
    stats = {
        "spam_reports": fast_query("SELECT COUNT(*) FROM chain_spam_reports")[0]['count'],
        "fake_accounts": fast_query("SELECT COUNT(*) FROM chain_profiles WHERE is_fake = TRUE")[0]['count'],
        "banned_users": fast_query("SELECT COUNT(*) FROM chain_profiles WHERE deleted_at IS NOT NULL")[0]['count']
    }
    
    reports = fast_query("""
        SELECT r.*, reporter.username as reporter_username, target.username as target_username
        FROM chain_spam_reports r
        JOIN chain_profiles reporter ON r.reporter_profile_id = reporter.id
        JOIN chain_profiles target ON r.target_profile_id = target.id
        ORDER BY r.created_at DESC
        LIMIT 20
    """)
    
    return render_template("admin/safety.html", stats=stats, reports=reports, profile=profile)

@admin_safety_bp.route('/detect-fake', methods=['POST'])
@login_required
def detect_fake():
    """Simple logic to detect fake accounts based on trust score and IP repetition."""
    # This would normally be a background job
    write_query("""
        UPDATE chain_profiles 
        SET is_fake = TRUE 
        WHERE trust_score < 0.3 OR last_ip IN (
            SELECT last_ip FROM chain_profiles 
            WHERE last_ip IS NOT NULL 
            GROUP BY last_ip 
            HAVING COUNT(*) > 5
        )
    """)
    return jsonify({"success": True, "message": "Fake account detection complete."})

@admin_safety_bp.route('/report', methods=['POST'])
@login_required
def report_spam():
    profile = get_current_profile()
    data = request.get_json(silent=True) or {}
    
    sql = """
        INSERT INTO chain_spam_reports (reporter_profile_id, target_profile_id, thread_id, reason, details)
        VALUES (%s, %s, %s, %s, %s)
    """
    write_query(sql, (profile['id'], data.get('target_id'), data.get('thread_id'), data.get('reason'), data.get('details')))
    return jsonify({"success": True})
