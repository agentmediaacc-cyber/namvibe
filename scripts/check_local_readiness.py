"""
Phase 68B — Local Deployment Readiness Check.
Verifies Python version, venv, Redis, DB connection, blueprints, templates, static files, .gitignore.
"""
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(label, condition, fatal=True):
    if condition:
        print(f"  ✅ {label}")
        return True
    print(f"  {'❌' if fatal else '⚠️'} {label}")
    if fatal:
        return False
    return True


def main():
    errors = 0
    print("=" * 60)
    print("CHAIN Local Readiness Check")
    print("=" * 60)

    # 1. Python version
    py = sys.version_info
    errors += 0 if check("Python >= 3.10", py.major >= 3 and py.minor >= 10) else 1

    # 2. Virtual env
    venv = os.environ.get("VIRTUAL_ENV") or os.environ.get("CONDA_PREFIX") or hasattr(sys, 'real_prefix')
    errors += 0 if check("Virtualenv active", bool(venv)) else 1

    # 3. Requirements installed
    req_file = ROOT / "requirements.txt"
    errors += 0 if check("requirements.txt exists", req_file.exists()) else 1

    if req_file.exists():
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q", "--dry-run"],
                capture_output=True, timeout=30
            )
            pip_ok = True
        except Exception:
            pip_ok = False
        errors += 0 if check("Requirements installable", pip_ok) else 1

    # 4. Redis reachable
    redis_ok = False
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), socket_timeout=2)
        redis_ok = r.ping()
    except Exception:
        pass
    check("Redis reachable", redis_ok, fatal=False)

    # 5. DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "")
    check("DATABASE_URL set", bool(db_url), fatal=False)

    # 6. SECRET_KEY
    sk = os.getenv("SECRET_KEY", "")
    check("SECRET_KEY set", bool(sk), fatal=False)

    # 7. Flask app imports
    app_ok = False
    try:
        sys.path.insert(0, str(ROOT))
        from app import create_app
        app_ok = True
    except Exception as e:
        print(f"  ❌ Flask app import failed: {e}")
    errors += 0 if check("Flask app imports cleanly", app_ok) else 1

    # 8. URL map loads
    if app_ok:
        try:
            app = create_app()
            routes = {rule.rule for rule in app.url_map.iter_rules()}
            check(f"URL map loaded ({len(routes)} routes)", len(routes) > 0)
        except Exception as e:
            print(f"  ❌ URL map load failed: {e}")
            errors += 1
    else:
        errors += 1

    # 9. Critical blueprints
    blueprints_needed = [
        "auth", "profile", "messages", "calls_v2", "feed", "notification_engine",
        "creator", "marketplace", "dating", "live", "wallet", "ai",
        "admin", "performance",
    ]
    if app_ok:
        try:
            bp_names = {bp.name for bp in app.blueprints.values()}
            for bp in blueprints_needed:
                found = bp in bp_names
                check(f"Blueprint '{bp}' registered", found)
                errors += 0 if found else 1
        except Exception as e:
            print(f"  ❌ Blueprint check failed: {e}")
            errors += 1

    # 10. Static folders
    for sp in ["static", "static/css", "static/js", "static/img"]:
        p = ROOT / sp
        check(f"Static folder '{sp}' exists", p.is_dir())

    # 11. Template folders
    tp = ROOT / "templates"
    if tp.is_dir():
        tdirs = [d.name for d in tp.iterdir() if d.is_dir()]
        check(f"Template dirs found ({len(tdirs)})", len(tdirs) > 0)
    else:
        check("templates/ exists", False)

    # 12. SQL phase files
    sql_dir = ROOT / "sql"
    if sql_dir.is_dir():
        sql_files = list(sql_dir.glob("*.sql"))
        check(f"SQL files found ({len(sql_files)})", len(sql_files) > 0)
    else:
        check("sql/ exists", False)

    # 13. .gitignore protects secrets/backups/uploads
    gitignore = ROOT / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        check(".gitignore has secrets/", "secrets/" in content)
        check(".gitignore has backups/", "backups/" in content)
        check(".gitignore has static/uploads/", "static/uploads/" in content)
    else:
        check(".gitignore exists", False)
        errors += 1

    # 14. Premium CSS / JS
    css_dir = ROOT / "static" / "css"
    if css_dir.is_dir():
        premium_css = list(css_dir.glob("*premium*"))
        check(f"Premium CSS files ({len(premium_css)})", len(premium_css) >= 10)

    js_dir = ROOT / "static" / "js"
    if js_dir.is_dir():
        premium_js = list(js_dir.glob("*premium*"))
        check(f"Premium JS files ({len(premium_js)})", len(premium_js) >= 8)

    print("=" * 60)
    if errors == 0:
        print(f"RESULT: ✅ All {errors} checks passed")
    else:
        print(f"RESULT: ❌ {errors} check(s) failed")
    print("=" * 60)
    return errors


if __name__ == "__main__":
    sys.exit(main())
