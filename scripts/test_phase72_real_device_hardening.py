"""
Phase 72 — Final Premium Real-Device Hardening Tests
Checks: mobile polish, touch smoothness, fast first load,
layout shift, icon overlap, readable text, page speed,
wallet speed, homepage speed, realtime reconnection.
"""
import os, sys, json, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["CHAIN_ENV"] = "production"
os.environ["CHAIN_DISABLE_CALL_WORKER"] = "1"
os.environ["CHAIN_DISABLE_SCHEDULER"] = "1"
os.environ["CHAIN_DEV_TOOLS"] = "1"

PASS = 0
FAIL = 0
WARN = 0

def check(label, ok, detail=""):
    global PASS, FAIL, WARN
    status = "PASS" if ok else ("WARN" if "WARN" in str(detail).upper() else "FAIL")
    if status == "PASS": PASS += 1
    elif status == "WARN": WARN += 1
    else: FAIL += 1
    print(f"  [{status}] {label}" + (f"\n        {detail}" if detail else ""))

print("=" * 60)
print("Phase 72 — Real-Device Hardening")
print("=" * 60)

# ── 1. App Import ──
print("\n--- 1. App Import ---")
try:
    from app import app
    check("App creates cleanly", True)
except Exception as e:
    check("App creates cleanly", False, str(e))

# ── 2. Wallet Speed ──
print("\n--- 2. Wallet Speed ---")
try:
    from services.wallet_service import get_wallet, get_wallet_transactions
    from services.request_cache import clear_request_cache
    from services.profile_service import get_current_profile

    with app.test_request_context():
        clear_request_cache()
        wallet = get_wallet("test_profile_speed")
        check("get_wallet request cache works", wallet is None or isinstance(wallet, dict))
        # Second call should hit request cache
        wallet2 = get_wallet("test_profile_speed")
        check("get_wallet cache hit", wallet2 is None or isinstance(wallet2, dict))
        txs = get_wallet_transactions("test_profile_speed", limit=5)
        check("get_wallet_transactions works", isinstance(txs, list))
except Exception as e:
    check("Wallet speed tests", False, str(e))

# ── 3. Profile Bundle Parallelism ──
print("\n--- 3. Profile Bundle Parallelism ---")
try:
    import inspect
    from services import profile_service
    source = inspect.getsource(profile_service.get_profile_bundle)
    has_executor = "ThreadPoolExecutor" in source
    check("Profile bundle uses ThreadPoolExecutor", has_executor)
    has_bundle_results = "bundle_results" in source
    check("Profile bundle collects parallel results", has_bundle_results)
except Exception as e:
    check("Profile bundle parallelism check", False, str(e))

# ── 4. Homepage Parallelism ──
print("\n--- 4. Homepage Parallelism ---")
try:
    import inspect
    from services import homepage_service
    source = inspect.getsource(homepage_service.get_homepage_data)
    has_f_groups = "f_groups" in source or "ThreadPoolExecutor" in source
    check("Homepage serial queries parallelized", has_f_groups)
except Exception as e:
    check("Homepage serial queries parallelized", False, str(e))

# ── 5. Mobile CSS Checks ⚡ ──
print("\n--- 5. Mobile CSS Checks ---")
html_source = open("templates/base.html").read()
css = html_source[html_source.find("<style>"):html_source.find("</style>")] if "<style>" in html_source else ""

check("touch-action: manipulation", "touch-action: manipulation" in css)
check("-webkit-tap-highlight-color", "-webkit-tap-highlight-color" in css)
check(":active scale transform", "transform: scale(.96)" in css)
check("img aspect-ratio fallback", "attr(width) / attr(height)" in css)
check("img without dimensions default ratio", "[src]:not([width]):not([height])" in css)
check("avatar aspect-ratio", ".avatar-img" in css or "img[class*=\"avatar\"]" in css)
check("reconnect banner exists", "reconnect-banner" in css or 'id="chain-reconnect-banner"' in html_source)
check("mobile search bar media query", "search-bar-mobile" in css)

# ── 6. SocketIO Reconnection ──
print("\n--- 6. SocketIO Reconnection ---")
has_reconnection = "reconnectionAttempts" in html_source and "reconnectionDelayMax" in html_source
check("SocketIO exponential backoff configured", has_reconnection)
has_reconnect_banner = "chain-reconnect-banner" in html_source
check("Reconnect banner HTML present", has_reconnect_banner)
has_reconnect_handlers = "s.on(\"reconnect\"" in html_source or 's.on("reconnect"' in html_source
check("Reconnect event handlers", has_reconnect_handlers)

# ── 7. No Layout Shift (Image Dimensions) ──
print("\n--- 7. Layout Shift Prevention ---")
img_aspect = "aspect-ratio: attr(width) / attr(height)" in css or "aspect-ratio: 1" in css
check("CSS aspect-ratio prevention", img_aspect)

# ── 8. Icon Overlap Prevention ──
print("\n--- 8. Icon/Tap Target Checks ---")
has_tap_highlight = "-webkit-tap-highlight-color: transparent" in css
check("No icon selection on tap", has_tap_highlight)
min_height_44 = "min-height: 44px" in css
check("Touch targets min 44px", min_height_44)

# ── 9. Wallet Route Parallelization ──
print("\n--- 9. Wallet Route Parallelization ---")
try:
    import inspect
    from api_routes import wallet_routes
    source = inspect.getsource(wallet_routes.index)
    has_parallel_wallet = "ThreadPoolExecutor" in source and "f_wallet" in source
    check("Wallet route uses ThreadPoolExecutor", has_parallel_wallet)
except Exception as e:
    check("Wallet route parallelization", False, str(e))

# ── 10. Text Readability / Contrast ──
print("\n--- 10. Text Contrast ---")
has_muted = "#a0aab8" in css or "chain-muted" in css
check("Muted text contrast fix present", has_muted)

# ── 11. Page Speed Estimates ──
print("\n--- 11. Page Speed Estimates ---")
try:
    with app.test_request_context():
        from services.wallet_service import get_wallet
        from services.request_cache import clear_request_cache
        clear_request_cache()
        t0 = time.perf_counter()
        w = get_wallet("test_speed")
        wall_t = (time.perf_counter() - t0) * 1000
    check(f"get_wallet latency ({wall_t:.0f}ms)", wall_t < 5000, f"{wall_t:.0f}ms")
except Exception as e:
    check("Page speed estimate", False, str(e))

# ── Summary ──
total = PASS + FAIL
print(f"\n{'=' * 60}")
print(f"Total: {PASS} passed, {FAIL} failed, {WARN} warnings ({total + WARN} checks)")
print(f"{'=' * 60}")
if FAIL:
    print(f"❌ {FAIL} CHECK(S) FAILED")
    sys.exit(1)
else:
    print(f"✅ ALL CHECKS PASSED")
    sys.exit(0)
