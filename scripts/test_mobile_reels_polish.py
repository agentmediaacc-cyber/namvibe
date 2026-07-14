from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOME_JS = (ROOT / "static" / "js" / "namvibe_home_pro.js").read_text()
HOME_CSS = (ROOT / "static" / "css" / "namvibe_home_pro.css").read_text()
PREMIUM_CSS = (ROOT / "static" / "css" / "namvibe_home_premium_v2.css").read_text()
TEMPLATE = (ROOT / "templates" / "chain_home.html").read_text()


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_preload_logic():
    assert_true("preloadAdjacentViewerVideos" in HOME_JS, "next video preload logic should exist")
    assert_true('preload = "metadata"' in HOME_JS or 'preload="metadata"' in HOME_JS, "videos should default to metadata preload")
    assert_true("video.removeAttribute(\"src\")" in HOME_JS, "far videos should unload when safe")
    assert_true("video.play().catch" in HOME_JS, "only active video should be allowed to play")


def test_double_tap_polish():
    assert_true("pendingLikeRequests" in HOME_JS, "duplicate like guard should exist")
    assert_true("nvpro-mobile-reel-heart" in HOME_JS + HOME_CSS, "floating heart should exist")
    assert_true("navigator.vibrate" in HOME_JS, "haptic feedback should be guarded")


def test_buffering_state():
    assert_true("data-mobile-buffer" in HOME_JS, "buffering spinner markup should exist")
    for token in ("waiting", "canplay", "loadeddata", "error"):
        assert_true(token in HOME_JS, f"buffer spinner should handle {token}")


def test_position_and_infinite_load():
    assert_true("namvibe:last_reel_index" in HOME_JS, "last reel index should be stored in sessionStorage")
    assert_true("maybeFetchMoreMobileReels" in HOME_JS, "infinite load trigger should exist")
    assert_true("You’re caught up." in HOME_JS or "You're caught up." in HOME_JS, "end message should exist")
    assert_true("nvpro-mobile-reel-slide-skeleton" in HOME_JS + HOME_CSS, "skeleton should exist")


def test_no_fake_words():
    lower = (HOME_JS + HOME_CSS + TEMPLATE).lower()
    for term in ("fake reel", "demo reel", "test reel"):
        assert_true(term not in lower, f"forbidden term leaked: {term}")


def test_css_safety():
    css = HOME_CSS + PREMIUM_CSS
    assert_true("prefers-reduced-motion" in css, "reduced motion handling should exist")
    assert_true("env(safe-area-inset-top" in css or "env(safe-area-inset-bottom" in css, "safe-area support should exist")
    assert_true("overflow-x: hidden" in css, "no horizontal overflow should be enforced")


if __name__ == "__main__":
    test_preload_logic()
    test_double_tap_polish()
    test_buffering_state()
    test_position_and_infinite_load()
    test_no_fake_words()
    test_css_safety()
    print("mobile reels polish: ok")
