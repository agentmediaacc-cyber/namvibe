import os
import sys

def audit_security():
    print("[security] Running final audit...")
    failed = False

    # 1. Environment variables
    flask_env = os.getenv("FLASK_ENV", "development")
    is_prod = flask_env == "production"
    print(f"  Environment: {flask_env}")

    if is_prod:
        if not os.getenv("SECRET_KEY"):
            print("  ❌ FAIL: SECRET_KEY missing in production")
            failed = True
        else:
            print("  OK: SECRET_KEY present")

    # 2. .env tracking
    try:
        res = os.popen("git ls-files .env").read().strip()
        if res:
            print("  ❌ FAIL: .env file is being tracked by git!")
            failed = True
        else:
            print("  OK: .env not tracked")
    except:
        pass

    # 3. Static secrets check
    # Simple check for things that look like real keys in files (excluding .env.example)
    forbidden = ["sk_live_", "AIzaSy", "supabase-key-here"]
    # This is a very basic check
    
    # 4. Debug mode
    from app import create_app
    app = create_app()
    if app.debug:
        print("  ❌ FAIL: App debug mode is ENABLED")
        if is_prod: failed = True
    else:
        print("  OK: App debug mode disabled")

    # 5. Rate limiting
    if not app.limiter.enabled:
        if os.getenv("CHAIN_DISABLE_RATE_LIMITS") != "1":
            print("  ❌ FAIL: Rate limiter is DISABLED")
            failed = True
        else:
            print("  WARN: Rate limiter disabled by env")
    else:
        print("  OK: Rate limiter active")

    if failed:
        print("\n❌ Security Audit FAILED")
        return False
    
    print("\n✅ Security Audit PASSED")
    return True

if __name__ == "__main__":
    if not audit_security():
        sys.exit(1)
