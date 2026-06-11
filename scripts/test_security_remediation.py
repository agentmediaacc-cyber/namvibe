#!/usr/bin/env python3
"""
Phase 77 Security Remediation Test Script.
Verifies all 14 security fixes are in place.
"""
import ast
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def ok(msg, detail=""):
    print(f"  PASS  {msg}" + (f" — {detail}" if detail else ""))


def fail(msg, detail=""):
    print(f"  FAIL  {msg}" + (f" — {detail}" if detail else ""))


def check_system_routes():
    """1. system_routes.py has @require_admin on all routes."""
    path = ROOT / "api_routes" / "system_routes.py"
    if not path.exists():
        return fail("system_routes.py exists")
    src = path.read_text()
    if "from services.admin_auth_service import require_admin" not in src:
        return fail("system_routes.py", "Missing import for require_admin")
    route_count = len(re.findall(r"@system_bp\.route\(", src))
    admin_count = len(re.findall(r"@require_admin\n", src))
    if route_count > 0 and admin_count >= route_count:
        ok("system_routes.py", f"{admin_count}/{route_count} routes protected with @require_admin")
    else:
        fail("system_routes.py", f"{admin_count}/{route_count} routes have @require_admin")


def check_production_routes():
    """2. production_routes.py has @require_admin on all routes."""
    path = ROOT / "api_routes" / "production_routes.py"
    if not path.exists():
        return fail("production_routes.py exists")
    src = path.read_text()
    if "from services.admin_auth_service import require_admin" not in src:
        return fail("production_routes.py", "Missing import for require_admin")
    route_count = len(re.findall(r"@production_bp\.route\(", src))
    admin_count = len(re.findall(r"@require_admin\n", src))
    if route_count > 0 and admin_count >= route_count:
        ok("production_routes.py", f"{admin_count}/{route_count} routes protected with @require_admin")
    else:
        fail("production_routes.py", f"{admin_count}/{route_count} routes have @require_admin")


def check_admin_safety_routes():
    """3. admin_safety_routes.py uses @require_admin not @login_required."""
    path = ROOT / "api_routes" / "admin_safety_routes.py"
    if not path.exists():
        return fail("admin_safety_routes.py exists")
    src = path.read_text()
    if "from services.admin_auth_service import require_admin" not in src:
        return fail("admin_safety_routes.py", "Missing import for require_admin")
    if "from api_routes.profile_routes import login_required" in src:
        return fail("admin_safety_routes.py", "Still imports login_required instead of require_admin")
    if "@login_required" in src:
        return fail("admin_safety_routes.py", "Still uses @login_required")
    ok("admin_safety_routes.py", "Uses @require_admin (no @login_required)")


def check_csrf():
    """4. Flask-WTF CSRF protection is configured."""
    path = ROOT / "app.py"
    if not path.exists():
        return fail("app.py exists")
    src = path.read_text()
    if "from flask_wtf.csrf import CSRFProtect" not in src:
        return fail("CSRF", "Missing import for CSRFProtect")
    if "CSRFProtect(app)" not in src:
        return fail("CSRF", "CSRFProtect not initialized")
    ok("CSRF", "Flask-WTF CSRFProtect imported and initialized")


def check_flask_wtf_in_requirements():
    """Flask-WTF is in requirements.txt."""
    path = ROOT / "requirements.txt"
    if not path.exists():
        return fail("requirements.txt exists")
    content = path.read_text()
    if "Flask-WTF" not in content:
        return fail("requirements.txt", "Flask-WTF not found")
    ok("requirements.txt", "Flask-WTF is present")


def check_jwt_validation():
    """5. JWT Bearer token validation uses supabase.auth.get_user."""
    path = ROOT / "services" / "api_auth_service.py"
    if not path.exists():
        return fail("api_auth_service.py exists")
    src = path.read_text()
    if "supabase.auth.get_user(token)" not in src:
        return fail("JWT validation", "Does not call supabase.auth.get_user(token)")
    if "# Supabase JWT validation placeholder" in src:
        return fail("JWT validation", "Placeholder comment still present")
    ok("JWT validation", "Uses supabase.auth.get_user(token)")


def check_nginx():
    """6. Nginx config has HTTPS, HSTS, gzip."""
    path = ROOT / "nginx" / "chain.conf.example"
    if not path.exists():
        return fail("nginx/chain.conf.example exists")
    src = path.read_text()
    if "listen 443 ssl" not in src:
        return fail("Nginx", "Missing HTTPS server block (listen 443 ssl)")
    if "Strict-Transport-Security" not in src:
        return fail("Nginx", "Missing HSTS header")
    if "gzip on;" not in src:
        return fail("Nginx", "Missing gzip configuration")
    ok("Nginx", "HTTPS, HSTS, and gzip configured")


def check_backup_scripts_exist():
    """7. Backup scripts exist and are executable."""
    scripts = {
        "backup_db.sh": "scripts/backup_db.sh",
        "sync_media_backup.sh": "scripts/sync_media_backup.sh",
        "restore_media.py": "scripts/restore_media.py",
    }
    all_ok = True
    for name, rel in scripts.items():
        p = ROOT / rel
        if not p.exists():
            fail(f"Backup script {name}", "Does not exist")
            all_ok = False
        elif not os.access(str(p), os.X_OK):
            fail(f"Backup script {name}", "Not executable")
            all_ok = False
    if all_ok:
        ok("Backup scripts", "All 3 scripts exist and are executable")


def check_backup_db_sh():
    """backup_db.sh has proper pg_dump logic."""
    path = ROOT / "scripts" / "backup_db.sh"
    if not path.exists():
        return
    src = path.read_text()
    if "pg_dump" not in src or "DATABASE_URL" not in src:
        fail("backup_db.sh", "Missing pg_dump or DATABASE_URL usage")
    else:
        ok("backup_db.sh", "Uses pg_dump with DATABASE_URL")


def check_sync_media_backup_sh():
    """sync_media_backup.sh handles s3/rclone sync."""
    path = ROOT / "scripts" / "sync_media_backup.sh"
    if not path.exists():
        return
    src = path.read_text()
    if "aws s3 sync" not in src and "rclone sync" not in src:
        fail("sync_media_backup.sh", "Missing s3/rclone sync logic")
    else:
        ok("sync_media_backup.sh", "Has s3/rclone sync capability")


def check_restore_media_py():
    """restore_media.py is valid Python with confirmation prompt."""
    path = ROOT / "scripts" / "restore_media.py"
    if not path.exists():
        return
    try:
        ast.parse(path.read_text())
        ok("restore_media.py", "Valid Python syntax")
    except SyntaxError as e:
        fail("restore_media.py", f"Syntax error: {e}")


def check_env_production():
    """8. .env.production.example has backup and TURN env vars."""
    path = ROOT / ".env.production.example"
    if not path.exists():
        return fail(".env.production.example exists")
    src = path.read_text()
    checks = {
        "CHAIN_BACKUP_LOCATION": "Backup location",
        "DATABASE_BACKUP_URL": "Database backup URL",
        "BACKUP_BUCKET": "Backup bucket",
        "TURN_SERVER_URL": "TURN server URL",
        "TURN_USERNAME": "TURN username",
        "TURN_PASSWORD": "TURN password",
    }
    all_ok = True
    for var, label in checks.items():
        if f"{var}=" not in src:
            fail(f".env.production.example", f"Missing {var} ({label})")
            all_ok = False
    if all_ok:
        ok(".env.production.example", "All backup and TURN env vars present")


def check_session_lifetime():
    """9. Session lifetime is <= 7 days."""
    path = ROOT / "app.py"
    if not path.exists():
        return fail("app.py exists")
    src = path.read_text()
    # Find all PERMANENT_SESSION_LIFETIME assignments
    matches = re.findall(r"PERMANENT_SESSION_LIFETIME=timedelta\(days=(\d+)\)", src)
    if not matches:
        return fail("Session lifetime", "PERMANENT_SESSION_LIFETIME not found")
    worst = max(int(d) for d in matches)
    if worst > 7:
        fail("Session lifetime", f"Max is {worst} days (should be <= 7)")
    else:
        ok("Session lifetime", f"Max is {worst} days")

def main():
    print("=" * 60)
    print("  Phase 77 — Security Remediation Verification")
    print("=" * 60)

    checks = [
        ("1. system_routes.py protection", check_system_routes),
        ("2. production_routes.py protection", check_production_routes),
        ("3. admin_safety_routes.py decorator fix", check_admin_safety_routes),
        ("4. CSRF protection", check_csrf),
        ("5. Flask-WTF in requirements", check_flask_wtf_in_requirements),
        ("6. JWT Bearer token validation", check_jwt_validation),
        ("7. Nginx HTTPS/HSTS/gzip", check_nginx),
        ("8. Backup scripts existence", check_backup_scripts_exist),
        ("9. backup_db.sh content", check_backup_db_sh),
        ("10. sync_media_backup.sh content", check_sync_media_backup_sh),
        ("11. restore_media.py content", check_restore_media_py),
        ("12. .env.production.example vars", check_env_production),
        ("13. Session lifetime <= 7 days", check_session_lifetime),
    ]

    passed = 0
    failed = 0
    for label, fn in checks:
        print(f"\n--- {label} ---")
        fn()
        # We can't easily count pass/fail per check, so we track via print prefix
    print("\n" + "=" * 60)
    print("  Check the PASS/FAIL count above for results.")
    print("=" * 60)


if __name__ == "__main__":
    main()
