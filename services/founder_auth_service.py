from datetime import datetime, timezone
from functools import wraps

from flask import redirect, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from services.neon_service import execute, fetch_all, fetch_one


def _utcnow():
    return datetime.now(timezone.utc)


def hash_password(password):
    return generate_password_hash(password, method='pbkdf2:sha256')


def verify_password(password, password_hash):
    if not password or not password_hash:
        return False
    try:
        return check_password_hash(password_hash, password)
    except Exception:
        return False


def get_founder_by_username(username):
    cleaned = (username or "").strip().lower()
    if not cleaned:
        return None
    rows = fetch_all(
        "SELECT * FROM chain_founder WHERE LOWER(username) = %s LIMIT 1",
        (cleaned,), timeout_ms=30000
    )
    return rows[0] if rows else None


def get_founder_by_id(founder_id):
    rows = fetch_all(
        "SELECT * FROM chain_founder WHERE id = %s LIMIT 1",
        (founder_id,), timeout_ms=30000
    )
    return rows[0] if rows else None


def authenticate_founder(username, password):
    founder = get_founder_by_username(username)
    if not founder:
        return False, "Account not found."
    if not verify_password(password, founder.get("password_hash")):
        return False, "Invalid username or password."
    return True, founder


def login_founder_session(founder):
    session["founder_id"] = founder.get("id")
    session["founder_username"] = founder.get("username")
    session["founder_must_change"] = bool(founder.get("must_change_password", True))
    execute(
        "UPDATE chain_founder SET last_login_at = %s WHERE id = %s",
        (_utcnow().isoformat(), founder.get("id")), timeout_ms=30000
    )


def logout_founder_session():
    session.pop("founder_id", None)
    session.pop("founder_username", None)
    session.pop("founder_must_change", None)


def current_founder():
    founder_id = session.get("founder_id")
    if not founder_id:
        return None
    return get_founder_by_id(founder_id)


def update_founder_password(founder_id, new_password):
    if len(new_password or "") < 8:
        return False, "Password must be at least 8 characters."
    hashed = hash_password(new_password)
    execute(
        "UPDATE chain_founder SET password_hash = %s, must_change_password = FALSE, is_first_login = FALSE, updated_at = %s WHERE id = %s",
        (hashed, _utcnow().isoformat(), founder_id), timeout_ms=30000
    )
    return True, "Password updated."


def update_founder_profile(founder_id, data):
    allowed = {"full_name", "email", "phone", "avatar_url", "two_factor_enabled", "two_factor_secret"}
    sets = []
    params = []
    for key, val in data.items():
        if key in allowed:
            sets.append(f"{key} = %s")
            params.append(val)
    if not sets:
        return False
    sets.append("updated_at = %s")
    params.append(_utcnow().isoformat())
    params.append(founder_id)
    sql = f"UPDATE chain_founder SET {', '.join(sets)} WHERE id = %s"
    execute(sql, tuple(params), timeout_ms=30000)
    return True


def require_founder(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("founder_id"):
            return redirect(f"/system/login?next={request.path}")
        founder = current_founder()
        if not founder:
            logout_founder_session()
            return redirect(f"/system/login?next={request.path}")
        if founder.get("must_change_password") and request.endpoint not in ("founder.setup", "founder.logout"):
            return redirect("/system/setup")
        return view_func(*args, **kwargs)
    return wrapped
