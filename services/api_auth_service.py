import functools
from flask import request, session, jsonify, g
from services.profile_service import get_current_profile
from services.auth_service import get_current_user

def api_login_required(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Try Session
        user_id = session.get("auth_user_id")
        
        # 2. Try Bearer Token
        auth_header = request.headers.get("Authorization")
        if not user_id and auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                from services.supabase_client import get_supabase
                supabase = get_supabase()
                user_resp = supabase.auth.get_user(token)
                if user_resp and user_resp.user:
                    session["auth_user_id"] = user_resp.user.id
                    user_id = user_resp.user.id
            except Exception:
                pass

        if not user_id:
            return jsonify({
                "success": False, 
                "error": {"code": "unauthorized", "message": "API authentication required"}
            }), 401
            
        # Ensure profile exists
        profile = get_current_profile()
        if not profile:
            return jsonify({
                "success": False, 
                "error": {"code": "profile_missing", "message": "Complete your profile first"}
            }), 403
            
        g.api_user = profile
        return f(*args, **kwargs)
    return decorated_function

def optional_api_user(f):
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        g.api_user = get_current_profile()
        return f(*args, **kwargs)
    return decorated_function

def api_response(data=None, meta=None, status=200):
    return jsonify({
        "success": True,
        "data": data,
        "meta": meta
    }), status

def api_error(message, code="internal_error", status=400):
    return jsonify({
        "success": False,
        "error": {
            "code": code,
            "message": message
        }
    }), status
