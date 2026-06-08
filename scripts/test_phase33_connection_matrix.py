#!/usr/bin/env python3
"""Phase 33 — Connection Matrix Test."""

import os
import sys
import subprocess
import importlib.util

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pass_count = 0
fail_count = 0

def test(name, condition):
    global pass_count, fail_count
    if condition:
        print(f"  [PASS] {name}")
        pass_count += 1
    else:
        print(f"  [FAIL] {name}")
        fail_count += 1

print("=== Phase 33 Connection Matrix Test ===")

# 1. All Python files compile
python_dirs = [
    os.path.join(BASE, "services"),
    os.path.join(BASE, "api_routes"),
    os.path.join(BASE, "scripts"),
]
compile_errors = []
for pd in python_dirs:
    if not os.path.isdir(pd):
        continue
    for fname in sorted(os.listdir(pd)):
        if fname.endswith(".py") and not fname.startswith("test_"):
            fpath = os.path.join(pd, fname)
            try:
                result = subprocess.run(
                    ["python3", "-m", "py_compile", fpath],
                    capture_output=True, text=True, timeout=15
                )
                if result.returncode != 0:
                    compile_errors.append(f"{fname}: {result.stderr.strip()}")
            except Exception as e:
                compile_errors.append(f"{fname}: {e}")

test("All phase33 files compile", len(compile_errors) == 0)
for err in compile_errors[:3]:
    print(f"  Compile error: {err}")

# 2. app.py compiles
app_py = os.path.join(BASE, "app.py")
if os.path.exists(app_py):
    result = subprocess.run(
        ["python3", "-m", "py_compile", app_py],
        capture_output=True, text=True, timeout=15
    )
    test("app.py compiles", result.returncode == 0)
    if result.returncode != 0:
        print(f"  {result.stderr.strip()}")

# 3. Route audit runs
audit_path = os.path.join(BASE, "scripts/audit_chain_routes.py")
if os.path.exists(audit_path):
    result = subprocess.run(
        ["python3", audit_path],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "PYTHONPATH": BASE}
    )
    output = result.stdout + result.stderr
    test("Route audit runs without crash", result.returncode == 0)
    if "duplicate" in output.lower():
        test("No duplicate routes", "no duplicate" in output.lower() or "0 duplicate" in output.lower())
    test("Route audit produces output", len(output) > 50)
else:
    test("Route audit script exists", False)

# 4. Key service functions exist
services_dir = os.path.join(BASE, "services")
service_files = [f for f in os.listdir(services_dir) if f.endswith(".py") and not f.startswith("__")]
key_services = [
    "auth_service", "profile_service", "neon_service", "redis_service",
    "push_notification_service", "call_service", "live_service",
    "wallet_engine", "notification_service", "notification_engine",
    "content_service", "homepage_service", "socketio_service",
    "socket_events", "group_feature_service", "supabase_client",
    "metrics_service", "request_cache",
]
for ks in key_services:
    found = any(ks in sf for sf in service_files)
    test(f"Service exists: {ks}.py", found)

# 5. Key route files exist
routes_dir = os.path.join(BASE, "api_routes")
route_files = [f for f in os.listdir(routes_dir) if f.endswith(".py") and not f.startswith("__")]
key_routes = [
    "auth_routes", "profile_routes", "message_routes", "call_routes",
    "live_routes", "wallet_routes", "push_routes", "feed_routes",
    "discovery_routes", "search_routes", "notification_routes",
    "safety_routes", "creator_routes", "post_routes", "reels_routes",
    "status_routes", "dating_routes", "matching_routes", "marketplace_routes",
    "verification_routes", "moderation_routes", "admin_routes",
]
for kr in key_routes:
    found = any(kr in rf for rf in route_files)
    test(f"Route exists: {kr}.py", found)

# 6. Key templates exist
templates_root = os.path.join(BASE, "templates")
all_templates = set()
for root, dirs, files in os.walk(templates_root):
    for f in files:
        if f.endswith(".html"):
            rel = os.path.relpath(os.path.join(root, f), templates_root)
            all_templates.add(rel)

key_templates = [
    "base.html", "chain_home.html",
    "settings/notifications.html",
]
for kt in key_templates:
    test(f"Template exists: {kt}", kt in all_templates)

# Template directories
template_dirs = set()
for root, dirs, files in os.walk(templates_root):
    for d in dirs:
        template_dirs.add(d)
key_dirs = ["auth", "messages", "calls", "live", "creator", "profile", "settings", "wallet", "notifications", "discover", "reels", "status", "safety", "dating", "posts", "marketplace", "admin", "chat", "dashboard"]
for kd in key_dirs:
    found = kd in template_dirs
    test(f"Template directory exists: {kd}/", found)

# 7. SQL files exist
sql_dir = os.path.join(BASE, "sql")
if os.path.isdir(sql_dir):
    sql_files = [f for f in os.listdir(sql_dir) if f.endswith(".sql")]
    test("SQL migration files exist", len(sql_files) > 0)

# 8. Key test files exist
scripts_dir = os.path.join(BASE, "scripts")
test_files = [f for f in os.listdir(scripts_dir) if f.endswith(".py") and "test_" in f]
test("Phase32 push tests exist", "test_phase32_push_notifications" in str(test_files))
test("Phase32 performance tests exist", "test_phase32_performance_guards" in str(test_files))
test("Phase33 color test exists", "test_phase33_color_system" in str(test_files))
test("Phase33 public pages test exists", "test_phase33_public_pages_visual" in str(test_files))
test("Phase33 connection matrix test exists", "test_phase33_connection_matrix" in str(test_files))
test("Route audit exists", "audit_chain_routes" in str(test_files))
test("Color audit exists", "audit_phase33_colors" in str(test_files))
test("Feature connection audit exists", "audit_phase33_feature_connections" in str(test_files))

# 9. Validate no duplicate CSS variables
all_css_vars = {}
for root, dirs, files in os.walk(os.path.join(BASE, "static/css")):
    for f in files:
        if f.endswith(".css"):
            fpath = os.path.join(root, f)
            with open(fpath) as fh:
                for line in fh:
                    if "--chain-" in line or "--px-" in line:
                        parts = line.strip().split(":")
                        if len(parts) >= 2:
                            var = parts[0].strip()
                            if var.startswith("--"):
                                if var in all_css_vars:
                                    all_css_vars[var].append(f)
                                else:
                                    all_css_vars[var] = [f]

duplicates = {k: v for k, v in all_css_vars.items() if len(v) > 1 and k.startswith("--chain-")}
test("No duplicate --chain- variable definitions", len(duplicates) == 0)
if duplicates:
    for k, v in list(duplicates.items())[:3]:
        print(f"  Duplicate {k} in {v}")

# 10. Check CSS variables match between files
chain_theme_path = os.path.join(BASE, "static/css/chain_theme.css")
if os.path.exists(chain_theme_path):
    with open(chain_theme_path) as f:
        theme_css = f.read()
    # Verify no old color system values remain
    for old_val in ["#F4F7FB", "#0B1B33", "#1E88E5", "#F7B733"]:
        if old_val in theme_css:
            test(f"No old color {old_val} in chain_theme.css", False)
            break
    else:
        test("No old color system values in chain_theme.css", True)

print(f"\nResults: {pass_count}/{pass_count + fail_count} passed, {fail_count}/{pass_count + fail_count} failed")
sys.exit(0 if fail_count == 0 else 1)
