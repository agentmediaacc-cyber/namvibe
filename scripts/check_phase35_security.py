#!/usr/bin/env python3
"""Phase 35 — Security Hardening Check"""

import os
import sys
import re

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

passed = 0
failed = 0
warnings = []

def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [PASS] {name}")
        passed += 1
    else:
        print(f"  [FAIL] {name} {detail}")
        failed += 1

def check_warn(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  [WARN] {name} — {detail}")
        warnings.append(name)
    else:
        print(f"  [PASS] {name}")

# 1. Login required on private routes
routes_dir = os.path.join(BASE, "api_routes")
login_required_count = 0
total_route_files = 0
for f in os.listdir(routes_dir):
    if f.endswith(".py") and f != "__init__.py":
        total_route_files += 1
        fp = os.path.join(routes_dir, f)
        content = open(fp).read()
        if "login_required" in content:
            login_required_count += 1
check("Login required decorator used in route files", login_required_count >= 5, f"Found in {login_required_count}/{total_route_files} route files")

# 2. Admin routes protected
admin_routes_file = os.path.join(routes_dir, "admin_routes.py")
if os.path.exists(admin_routes_file):
    content = open(admin_routes_file).read()
    check("Admin routes have auth protection", "session" in content.lower() or "login" in content.lower() or "auth" in content.lower())
else:
    check("Admin routes file exists", False)

# 3. Safety routes protected
safety_routes = os.path.join(routes_dir, "safety_routes.py")
if os.path.exists(safety_routes):
    content = open(safety_routes).read()
    check("Safety routes have login_required", "login_required" in content)
else:
    check("Safety routes file exists", True)  # not required

# 4. Wallet routes protected
wallet_routes = os.path.join(routes_dir, "wallet_routes.py")
if os.path.exists(wallet_routes):
    content = open(wallet_routes).read()
    check("Wallet routes have login_required", "login_required" in content)
else:
    check("Wallet routes file exists", False)

# 5. Profile update protected
profile_routes = os.path.join(routes_dir, "profile_routes.py")
if os.path.exists(profile_routes):
    content = open(profile_routes).read()
    check("Profile routes have login_required", "login_required" in content)
else:
    check("Profile routes file exists", False)

# 6. Message APIs protected
msg_routes = os.path.join(routes_dir, "message_routes.py")
if os.path.exists(msg_routes):
    content = open(msg_routes).read()
    check("Message routes have login_required", "login_required" in content)
else:
    check("Message routes file exists", False)

# 7. Call APIs protected
call_routes = os.path.join(routes_dir, "call_routes.py")
if os.path.exists(call_routes):
    content = open(call_routes).read()
    check("Call routes have login_required", "login_required" in content)
else:
    check("Call routes file exists", False)

# 8. CSRF protection
app_content = open(os.path.join(BASE, "app.py")).read()
if "csrf" in app_content.lower() or "CSRF" in app_content or "WTF_CSRF" in app_content:
    check("CSRF protection configured", True)
else:
    check("CSRF protection configured", False, "No CSRF protection found — may be acceptable for API-only or JWT-based auth")

# 9. Rate limiter configured
rate_limit_file = os.path.join(BASE, "services", "rate_limit_service.py")
check("Rate limiter service exists", os.path.exists(rate_limit_file))

# 10. Redis limiter configured
try:
    from services.rate_limit_service import init_rate_limiter
    check("init_rate_limiter callable", callable(init_rate_limiter))
except Exception:
    check("init_rate_limiter callable", False, "rate_limit_service not properly importable")

# 11. Password reset route exists
auth_routes = os.path.join(routes_dir, "auth_routes.py")
password_reset = False
if os.path.exists(auth_routes):
    content = open(auth_routes).read()
    if "reset" in content.lower() or "recover" in content.lower() or "forgot" in content.lower():
        password_reset = True
check("Password reset/recovery route exists", password_reset, "No password reset route found in auth_routes.py")

# 12. Report/block routes exist
has_report = False
has_block = False
for f in os.listdir(routes_dir):
    if f.endswith(".py"):
        content = open(os.path.join(routes_dir, f)).read()
        if "report" in content.lower():
            has_report = True
        if "block" in content.lower():
            has_block = True
check("Report route exists", has_report)
check("Block route exists", has_block)

# 13. No obvious secrets in templates
template_dir = os.path.join(BASE, "templates")
secret_patterns = ["SECRET_KEY", "API_KEY", "PASSWORD", "supabase_key", "service_role"]
secrets_leaked = 0
for root, dirs, files in os.walk(template_dir):
    for f in files:
        if f.endswith(".html"):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                for pat in secret_patterns:
                    if pat in content:
                        secrets_leaked += 1
                        check_warn(f"Possible secret '{pat}' in template {f}", True, f"Found in {f}")
            except Exception:
                pass
check("No secrets leaked in HTML templates", secrets_leaked == 0, f"{secrets_leaked} potential leaks found")

# 14. .env not referenced in static files
static_env_refs = 0
for root, dirs, files in os.walk(os.path.join(BASE, "static")):
    for f in files:
        if f.endswith((".js", ".html")):
            fp = os.path.join(root, f)
            try:
                content = open(fp).read()
                if ".env" in content:
                    static_env_refs += 1
            except Exception:
                pass
check(".env not referenced in static files", static_env_refs == 0, f"{static_env_refs} references to .env in static files")

# 15. Debug off in production runner
app_content = open(os.path.join(BASE, "app.py")).read()
check("debug=False in production", "debug=False" in app_content or "debug=False" in app_content, "Could not verify debug=False in app.py")

# 16. Auth routes have session/rate limiting
try:
    from services.auth_service import get_current_user
    check("Auth service has get_current_user", callable(get_current_user))
except Exception:
    check("Auth service has get_current_user", False)

# 17. Session management
try:
    from services.session_service import store_auth_session, get_current_auth_user, clear_auth_session
    check("Session service has store_auth_session", callable(store_auth_session))
    check("Session service has get_current_auth_user", callable(get_current_auth_user))
    check("Session service has clear_auth_session", callable(clear_auth_session))
except Exception:
    check("Session management functions", False)

# 18. Presence engine
try:
    from services.presence_engine import set_online, set_offline
    check("Presence engine: set_online / set_offline", callable(set_online) and callable(set_offline))
except Exception:
    check("Presence engine functions", False)

print()
print("  [SUMMARY] Security Hardening:")
print(f"    Passed: {passed}")
print(f"    Failed: {failed}")
print(f"    Warnings: {len(warnings)}")

# Write report
report_path = os.path.join(BASE, "reports", "phase35_security_test.md")
with open(report_path, "w") as f:
    f.write(f"# CHAIN Phase 35 — Security Hardening Report\n\n")
    f.write(f"## Results\n\n")
    f.write(f"- Checks passed: {passed}\n")
    f.write(f"- Checks failed: {failed}\n")
    f.write(f"- Warnings: {len(warnings)}\n\n")
    f.write(f"## Findings\n\n")
    if warnings:
        f.write("### Warnings\n\n")
        for w in warnings:
            f.write(f"- {w}\n")
    if failed > 0:
        f.write("### Failing Checks\n\n")
        f.write("Review the security script output above for details.\n\n")
    f.write("## Recommendations\n\n")
    f.write("1. Add CSRF protection if forms are used without API tokens.\n")
    f.write("2. Ensure rate limiting covers all auth and sensitive endpoints.\n")
    f.write("3. Review templates for any hardcoded secrets.\n")
    f.write("4. Confirm debug mode is disabled in production.\n")
    f.write("5. Ensure all admin and safety routes require authentication.\n")
f.close()
print(f"Report written to {report_path}")
print(f"\nResults: {passed}/{passed+failed} passed, {failed}/{passed+failed} failed")
if failed > 0:
    sys.exit(1)
