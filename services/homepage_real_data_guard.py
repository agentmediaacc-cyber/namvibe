"""Phase 73: Filter test/demo content from homepage sections.

Respects CHAIN_SHOW_TEST_CONTENT env var — when set to '1' or 'true',
all content (including test users) is shown. Default: hide test content.

Phase 87e expansion: comprehensive test/debug patterns covering:
- Usernames: debug, test, ui_test, tester, debug_test
- Display names: Test, Tester, UI Test, Debug
- Content: test, debug, UI Test, Promo test
- Emails: containing test/debug
- Profile flags: sandbox, dev, test
"""
import os
import re

from services.production_content_guard import is_fake_content

# ── Comprehensive test/demo username patterns ──
_TEST_USER_PATTERNS = [
    re.compile(r"^chain_(star|moon|gold|million|premium)$", re.I),
    re.compile(r"^phase8_", re.I),
    re.compile(r"^devsetup_", re.I),
    re.compile(r"^testuser", re.I),
    re.compile(r"^test_", re.I),
    re.compile(r"^partner$", re.I),
    re.compile(r"^demo_", re.I),
    re.compile(r"^dev_", re.I),
    re.compile(r".*seed.*", re.I),
    # Phase 87e: additional user patterns
    re.compile(r"debug_test", re.I),
    re.compile(r"ui_test", re.I),
    re.compile(r"tester", re.I),
    re.compile(r"debug", re.I),
]

# ── Email patterns for test accounts ──
_TEST_EMAIL_PATTERNS = [
    re.compile(r"@chain\.local$", re.I),
    re.compile(r"\.local$", re.I),
    re.compile(r"test", re.I),        # any email with "test" in it
    re.compile(r"debug", re.I),        # any email with "debug" in it
]

# ── Display name patterns for test/debug content ──
_TEST_DISPLAY_PATTERNS = [
    re.compile(r"\bTest\b", re.I),
    re.compile(r"\bTester\b", re.I),
    re.compile(r"\bUI Test\b", re.I),
    re.compile(r"\bDebug\b", re.I),
    re.compile(r"Promo.*UI Test", re.I),
    re.compile(r"phase\s*8\s*persistence", re.I),
    re.compile(r"phase8", re.I),
    re.compile(r"production\s*reel", re.I),
    re.compile(r"test\s*reel", re.I),
    re.compile(r"seed", re.I),
]

# ── Content/caption/body patterns for test/debug ──
_TEST_CONTENT_PATTERNS = [
    re.compile(r"\btest\b", re.I),
    re.compile(r"\bdebug\b", re.I),
    re.compile(r"\bUI Test\b", re.I),
    re.compile(r"Promo.*UI Test", re.I),
    re.compile(r"Real JPEG upload test", re.I),
    re.compile(r"Test photo caption", re.I),
    re.compile(r"Promo test", re.I),
    re.compile(r"phase\s*8\s*production\s*(post|reel)", re.I),
    re.compile(r"production\s*reel", re.I),
    re.compile(r"test\s*reel", re.I),
    re.compile(r"original\s*sound", re.I),
    re.compile(r"seed", re.I),
    re.compile(r"lorem\s*ipsum", re.I),
    re.compile(r"test\s*post", re.I),
]

_SHOW_ALL = (
    os.environ.get("CHAIN_SHOW_TEST_CONTENT", "0").lower() in ("1", "true", "yes")
    or (
        os.environ.get("CHAIN_FAST_LOCAL") == "1"
        and os.environ.get("FLASK_ENV", "development") != "production"
    )
)


def is_test_profile(profile):
    """Check if a profile is a test/demo account.
    
    To be used for filtering content from public homepage surfaces.
    Admin/dev users should see test content only in admin tools.
    """
    if _SHOW_ALL:
        return False
    username = (profile.get("username") or "").strip().lower()
    email = (profile.get("email") or profile.get("normalized_email") or "").strip().lower()
    
    # Check username patterns
    for pat in _TEST_USER_PATTERNS:
        if pat.search(username):
            return True
    
    # Check email patterns  
    for pat in _TEST_EMAIL_PATTERNS:
        if pat.search(email):
            return True
    
    # Check profile feature flags
    if profile.get("is_test_account") is True or profile.get("is_demo_account") is True:
        return True
    if profile.get("production_visible") is False:
        return True
    if profile.get("is_sandbox") is True or profile.get("sandbox") is True:
        return True
    if profile.get("dev_account") is True or profile.get("is_dev") is True:
        return True
    
    # Check display name
    display_name = (profile.get("display_name") or "").strip()
    for pat in _TEST_DISPLAY_PATTERNS:
        if pat.search(display_name):
            return True
    full_name = (profile.get("full_name") or "").strip()
    if full_name and full_name != display_name:
        for pat in _TEST_DISPLAY_PATTERNS:
            if pat.search(full_name):
                return True
    
    return False


def is_test_content(item):
    """Check if a content item (post, reel, story) is test/debug."""
    if _SHOW_ALL:
        return False
    if is_fake_content(item):
        return True
    
    # Check associated profile info
    profile_bits = {
        "username": item.get("username") or item.get("p_username"),
        "display_name": item.get("display_name") or item.get("p_display_name"),
        "email": item.get("email") or item.get("normalized_email"),
        "full_name": item.get("full_name"),
    }
    if is_test_profile(profile_bits):
        return True
    
    # Check content fields
    values = [
        item.get("caption"),
        item.get("body"),
        item.get("text"),
        item.get("title"),
        item.get("excerpt"),
        item.get("music_title"),
        " ".join(item.get("hashtags") or []) if isinstance(item.get("hashtags"), list) else item.get("hashtags"),
    ]
    haystack = " ".join(str(value or "") for value in values)
    if any(pat.search(haystack) for pat in _TEST_CONTENT_PATTERNS):
        return True
    
    # Check username from profile_id if available
    username = (item.get("username") or "").strip().lower()
    if any(pat.search(username) for pat in _TEST_USER_PATTERNS):
        return True
    
    return False


def filter_feed_posts(posts, profile_map=None):
    """Filter test/demo posts from a feed list."""
    if _SHOW_ALL:
        return posts
    result = []
    for p in posts:
        pid = p.get("profile_id")
        if pid and profile_map:
            profile = profile_map.get(pid) or {}
            if is_test_profile(profile):
                continue
        
        # Check username
        username = (p.get("username") or "").strip().lower()
        if any(pat.search(username) for pat in _TEST_USER_PATTERNS):
            continue
        
        # Check email
        email = (p.get("email") or p.get("normalized_email") or "").strip().lower()
        if any(pat.search(email) for pat in _TEST_EMAIL_PATTERNS):
            continue
        
        # Check display name
        display_name = (p.get("display_name") or "").strip()
        if any(pat.search(display_name) for pat in _TEST_DISPLAY_PATTERNS):
            continue
        
        # Check content
        content = (p.get("caption") or p.get("excerpt") or p.get("text") or p.get("body") or "").strip()
        if any(pat.search(content) for pat in _TEST_CONTENT_PATTERNS):
            continue
        
        result.append(p)
    return result


def filter_content(items, profile_map=None):
    """Filter test/demo items from any content list."""
    if _SHOW_ALL:
        return items
    result = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        pid = item.get("profile_id")
        if pid and profile_map and is_test_profile(profile_map.get(pid) or {}):
            continue
        if is_test_content(item):
            continue
        result.append(item)
    return result


def filter_profiles(profiles):
    """Filter test/demo profiles from a list."""
    if _SHOW_ALL:
        return profiles
    return [p for p in profiles if not is_test_profile(p)]


def public_profile_sql(alias="chain_profiles"):
    """SQL condition for public profile surfaces.
    
    This is applied at the database level to exclude known test accounts
    from SQL queries serving public homepage content.
    """
    if _SHOW_ALL:
        return "1 = 1"
    prefix = f"{alias}." if alias else ""
    return (
        f"LOWER(COALESCE({prefix}username, '')) NOT IN "
        "('chain_star', 'chain_moon', 'chain_gold', 'chain_million', 'chain_premium') "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'demo_%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'dev_%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'test_%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'testuser%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'phase8_%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE '%%seed%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'devsetup_%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE '%%debug_test%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE '%%ui_test%%' "
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE '%%tester%%' "
        f"AND LOWER(COALESCE({prefix}email, '')) NOT LIKE '%%.local' "
        f"AND LOWER(COALESCE({prefix}email, '')) NOT LIKE '%%@chain.local'"
    )


def public_profile_subquery():
    """SQL subquery for content tables with profile_id ownership."""
    return f"SELECT id FROM chain_profiles WHERE {public_profile_sql('chain_profiles')}"