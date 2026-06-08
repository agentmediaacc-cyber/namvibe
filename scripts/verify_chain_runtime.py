import os, sys, time, subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

print("=== ENV ===")
for k in ["FLASK_ENV", "ENV", "CHAIN_FAST_LOCAL", "DATABASE_URL", "REDIS_URL"]:
    v = os.getenv(k)
    print(f"{k}: {'FOUND' if v and 'URL' in k else v}")

print("\n=== FLASK ROUTES ===")
from app import create_app
app = create_app()
routes = sorted(str(r.rule) for r in app.url_map.iter_rules())

needed = [
    "/system/api/cache-status",
    "/system/api/health",
    "/system/api/queue/stats",
    "/healthz",
    "/posts/create",
    "/reels/upload",
    "/status/create",
]

for route in needed:
    print(f"{route}: {'OK' if route in routes else 'MISSING'}")

print("\n=== SYSTEM ROUTES FOUND ===")
for r in routes:
    if r.startswith("/system"):
        print(r)

print("\n=== LOCAL HTTP CHECKS ===")
urls = [
    "http://127.0.0.1:5000/healthz",
    "http://127.0.0.1:5000/system/api/cache-status",
    "http://127.0.0.1:5000/system/api/queue/stats",
]

for url in urls:
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "-m", "5", "-i", url],
            text=True,
            stderr=subprocess.STDOUT,
        )
        first = out.splitlines()[0] if out else ""
        is_json = "application/json" in out[:300].lower()
        is_404 = "404 - Not Found" in out or "HTTP/1.1 404" in out
        print(f"{url}: {first} | json={is_json} | custom404={is_404}")
    except Exception as e:
        print(f"{url}: FAILED {e}")

print("\n=== HOMEPAGE SPEED ===")
for i in range(2):
    try:
        out = subprocess.check_output(
            ["curl", "-sS", "-m", "30", "-I", "http://127.0.0.1:5000/"],
            text=True,
            stderr=subprocess.STDOUT,
        )
        line = next((x for x in out.splitlines() if x.lower().startswith("x-response-time-ms")), "X-Response-Time-Ms: MISSING")
        print(f"homepage request {i+1}: {line}")
    except Exception as e:
        print(f"homepage request {i+1}: FAILED {e}")

print("\n=== WORKERS HEALTH ===")
try:
    out = subprocess.check_output(
        ["curl", "-sS", "-m", "5", "http://127.0.0.1:5000/healthz"],
        text=True,
    )
    print(out[:1000])
except Exception as e:
    print(f"healthz failed: {e}")

print("\n=== PHASE TESTS ===")
tests = [
    ["python", "scripts/test_phase7_content_routes.py"],
    ["python", "scripts/test_phase51_performance.py"],
]
for cmd in tests:
    print(f"\nRUN: {' '.join(cmd)}")
    p = subprocess.run(cmd, text=True)
    print(f"exit_code={p.returncode}")
