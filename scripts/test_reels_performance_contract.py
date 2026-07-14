"""Structural performance contract checks for NamVibe Reels."""

from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static/js/reels.js").read_text(encoding="utf-8")
SERVICE = (ROOT / "services/reels_service.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "api_routes/reels_routes.py").read_text(encoding="utf-8")
TEMPLATE = (ROOT / "templates/reels.html").read_text(encoding="utf-8")


def assert_true(expr, msg):
    if not expr:
        raise AssertionError(msg)


def main():
    assert_true("IntersectionObserver" in JS, "expected IntersectionObserver playback")
    assert_true("__NAMVIBE_REELS_INITIALIZED__" in JS, "expected init guard")
    assert_true("loadObserver" in JS, "expected infinite-load observer")
    assert_true("requestAnimationFrame" in JS, "expected rAF progress loop")
    assert_true("navigator.sendBeacon" in JS and "fetch(" in JS, "expected beacon fallback transport")
    assert_true("saveData" in JS, "expected save-data handling")
    assert_true("visibilitychange" in JS, "expected visibility handling")
    assert_true("function buildSlide" in JS and "innerHTML" not in JS, "expected DOM-building slide renderer without innerHTML")
    assert_true("data-next-cursor" in TEMPLATE and "data-has-more" in TEMPLATE, "expected cursor bootstrap in template")
    assert_true("SELECT r.*" in SERVICE and "JOIN chain_profiles p ON p.id = r.profile_id" in SERVICE, "expected batched creator join")
    assert_true("fast_query(query, params" in SERVICE, "expected bounded feed query")
    assert_true(
        "build_public_reels_feed_cache_key" in SERVICE and "cache_key" in SERVICE,
        "expected shared public feed cache-key builder",
    )
    assert_true("api_reels_feed" in ROUTES and "/api/reels/feed" in ROUTES, "expected feed endpoint")
    assert_true("next_cursor" in ROUTES, "expected cursor contract")
    assert_true("reels_feed_timing" in SERVICE and "reels_page_timing" in ROUTES, "expected timing instrumentation for perf diagnosis")

    print("TEST_OK reels performance contract")


if __name__ == "__main__":
    main()
