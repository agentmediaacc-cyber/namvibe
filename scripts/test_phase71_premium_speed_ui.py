"""
Phase 71 — Premium Speed + UI Polish Test.
Tests: query speed, indexes exist, page transitions, skeleton loaders,
premium cards, mobile layout, contrast, font sizes, touch targets.
"""
import json, os, sys, re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["CHAIN_DISABLE_CALL_WORKER"] = "1"
os.environ["CHAIN_DISABLE_SCHEDULER"] = "1"
os.environ["CHAIN_DEV_TOOLS"] = "1"

PASS = 0
FAIL = 0
WARN = 0


def check(label, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")


def warn(label, detail=""):
    global WARN
    WARN += 1
    msg = f"  [WARN] {label}"
    if detail:
        msg += f" -- {detail}"
    print(msg)


def main():
    global PASS, FAIL, WARN

    print("=" * 60)
    print("Phase 71 — Premium Speed + UI Polish")
    print("=" * 60)

    # ── 1. Import app ──
    print("\n--- 1. App Import ---")
    try:
        from app import create_app
        app = create_app()
        check("App creates cleanly", True)
    except Exception as e:
        check(f"App import: {e}", False)
        sys.exit(1)

    anon = app.test_client()

    # ── 2. Performance Indexes ──
    print("\n--- 2. Performance Indexes ---")
    try:
        from services.neon_service import fast_query
        expected_indexes = [
            "idx_p71_follows_follower_following_deleted",
            "idx_p71_messages_thread_delivery",
            "idx_p71_messages_thread_sender_unread",
            "idx_p71_notifications_recipient_event_created",
            "idx_p71_call_logs_profile_other_created",
            "idx_p71_wallet_tx_profile_type",
            "idx_p71_posts_profile_engagement",
            "idx_p71_reels_profile_created_desc",
            "idx_p71_stories_profile_active",
            "idx_p71_live_rooms_profile_status",
            "idx_p71_dating_likes_actor_target_created",
            "idx_p71_threads_updated_desc",
        ]
        for idx in expected_indexes:
            rows = fast_query(
                "SELECT indexname FROM pg_indexes WHERE indexname = %s",
                (idx,), timeout_ms=5000
            )
            check(f"Index '{idx}' exists", bool(rows))
    except Exception as e:
        check(f"Index check: {e}", False)

    # ── 3. Page Load Speed ──
    print("\n--- 3. Page Load Speed ---")
    import time
    pages = [
        "/",
        "/auth/login",
        "/auth/register",
        "/discover",
        "/system/api/health",
    ]
    for path in pages:
        try:
            start = time.time()
            resp = anon.get(path)
            elapsed = (time.time() - start) * 1000
            ok = resp.status_code in (200, 302, 308) and elapsed < 30000
            check(f"GET {path} ({elapsed:.0f}ms)", ok)
            if not ok:
                print(f"        status={resp.status_code} time={elapsed:.0f}ms")
        except Exception as e:
            check(f"GET {path}: {e}", False)

    # ── 4. API Response Speed ──
    print("\n--- 4. API Speed ---")
    try:
        start = time.time()
        resp = anon.get("/system/api/health")
        elapsed = (time.time() - start) * 1000
        check(f"Health API ({elapsed:.0f}ms)", elapsed < 30000 and resp.status_code == 200)
    except Exception as e:
        check(f"Health API: {e}", False)

    # ── 5. Skeleton Loaders ──
    print("\n--- 5. Skeleton Loaders ---")
    base_content = Path(ROOT / "templates" / "base.html").read_text()
    check("Skeleton CSS defined", ".skeleton" in base_content and "@keyframes shimmer" in base_content)
    check("Skeleton-text class", "skeleton-text" in base_content)
    check("Skeleton-card class", "skeleton-card" in base_content)
    check("Skeleton-avatar class", "skeleton-avatar" in base_content)

    # ── 6. Page Transitions ──
    print("\n--- 6. Page Transitions ---")
    check("Page fade-in animation", "page-fade-in" in base_content and "@keyframes fadeIn" in base_content)
    check("Content body has fade-in", "page-fade-in" in re.findall(r'class="[^"]*content-body[^"]*"', base_content)[0] if re.findall(r'class="[^"]*content-body[^"]*"', base_content) else "")

    # ── 7. Premium Cards ──
    print("\n--- 7. Premium Cards ---")
    check("Premium-card class", "premium-card" in base_content)
    check("Premium-card hover lift", "translateY(-2px)" in base_content)

    # ── 8. Mobile Layout ──
    print("\n--- 8. Mobile Layout ---")
    check("Mobile spacing @media", "@media (max-width: 760px)" in base_content)
    check("Mobile padding-bottom 80px", "padding: 0 12px 80px" in base_content or "padding-bottom: 80px" in base_content)

    # ── 9. Color Contrast ──
    print("\n--- 9. Color Contrast ---")
    check("chain-muted contrast fix", "#a0aab8" in base_content)
    check("Secondary text contrast", ".secondary-text" in base_content or "secondary-text" in base_content)

    # ── 10. Touch Targets ──
    print("\n--- 10. Touch Targets ---")
    check("Min-height 44px for buttons", "min-height: 44px" in base_content)

    # ── 11. Dashboard Query ──
    print("\n--- 11. Dashboard Query ---")
    try:
        dash_content = Path(ROOT / "api_routes" / "dashboard_routes.py").read_text()
        check("Dashboard posts LIMIT 200", "LIMIT 200" in dash_content)
    except Exception as e:
        check(f"Dashboard check: {e}", False)

    # ── 12. Messaging N+1 Fix ──
    print("\n--- 12. Messaging N+1 Fix ---")
    try:
        msg_content = Path(ROOT / "services" / "messaging_engine.py").read_text()
        check("Batch muted check", "profile_id, muted FROM chain_thread_members" in msg_content)
    except Exception as e:
        check(f"Messaging check: {e}", False)

    # ── 13. Homepage Parametrized SQL ──
    print("\n--- 13. Homepage SQL ---")
    try:
        hp_content = Path(ROOT / "services" / "homepage_service.py").read_text()
        check("Parameterized profile query", "list(unique)" in hp_content)
    except Exception as e:
        check(f"Homepage check: {e}", False)

    # ── Summary ──
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"Total: {PASS} passed, {FAIL} failed, {WARN} warnings ({total} checks)")
    print(f"{'=' * 60}")
    if FAIL:
        print(f"❌ {FAIL} CHECK(S) FAILED")
        sys.exit(1)
    else:
        print("✅ ALL CHECKS PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
