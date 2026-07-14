from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "templates" / "chain_home.html").read_text()
HOME_JS = (ROOT / "static" / "js" / "namvibe_home_pro.js").read_text()
PREMIUM_JS = (ROOT / "static" / "js" / "namvibe_home_premium_v2.js").read_text()
HOME_CSS = (ROOT / "static" / "css" / "namvibe_home_pro.css").read_text()
PREMIUM_CSS = (ROOT / "static" / "css" / "namvibe_home_premium_v2.css").read_text()


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_fullscreen_markup():
    assert_true('id="nvVideoOverlayShell"' in TEMPLATE, "fullscreen viewer shell should exist")
    assert_true('id="nvMobileReelsFeed"' in TEMPLATE, "mobile reels feed should exist")
    assert_true('id="nvMobileCommentsDrawer"' in TEMPLATE, "mobile comment drawer should exist")


def test_mobile_css():
    css = HOME_CSS + PREMIUM_CSS
    assert_true("100dvh" in css and "100vh" in css, "mobile fullscreen height should use 100vh and 100dvh")
    assert_true("scroll-snap-type: y mandatory" in css, "mobile viewer should use vertical snap")
    assert_true("scroll-snap-align: start" in css, "mobile slides should align to snap start")
    assert_true("object-fit: cover" in css, "mobile videos should use object-fit cover")
    assert_true(".nvpro-mobile-reel-rail" in css, "right action rail should exist")


def test_mobile_js_behavior():
    js = HOME_JS + PREMIUM_JS
    assert_true("toggleMobileViewerPlayback" in HOME_JS, "tap pause/play handler should exist")
    assert_true("lastTapVideoId" in HOME_JS and "animateMobileHeart" in HOME_JS, "double-tap like handler should exist")
    assert_true("IntersectionObserver" in HOME_JS and "video.pause()" in HOME_JS, "offscreen videos should pause via IntersectionObserver")
    assert_true("openMobileComments" in HOME_JS and "submitMobileComment" in HOME_JS, "comment drawer handlers should exist")
    assert_true("navigator.share" in HOME_JS, "share should prefer navigator.share")
    assert_true("collectMobileViewerItems" in HOME_JS, "viewer should use real homepage video data")


def test_no_fake_video_data():
    lower = (TEMPLATE + HOME_JS + HOME_CSS).lower()
    for term in ("fake reel", "demo reel", "mock reel", "placeholder reel"):
        assert_true(term not in lower, f"forbidden fake mobile video term leaked: {term}")


if __name__ == "__main__":
    test_fullscreen_markup()
    test_mobile_css()
    test_mobile_js_behavior()
    test_no_fake_video_data()
    print("mobile reels tiktok experience: ok")
