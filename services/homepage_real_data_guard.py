"""Phase 73: Filter test/demo content from homepage sections.

Respects CHAIN_SHOW_TEST_CONTENT env var — when set to '1' or 'true',
all content (including test users) is shown. Default: hide test content.
"""
import os
import re

_TEST_USER_PATTERNS = [
    re.compile(r"^chain_(star|moon|gold|million|premium)$", re.I),
    re.compile(r"^phase8_", re.I),
    re.compile(r"^devsetup_", re.I),
    re.compile(r"^testuser", re.I),
    re.compile(r"^test_", re.I),
    re.compile(r"^partner$", re.I),
    re.compile(r"^demo_", re.I),
    re.compile(r"^dev_", re.I),
]

_TEST_EMAIL_PATTERNS = [
    re.compile(r"@chain\.local$", re.I),
    re.compile(r"\.local$", re.I),
]

_SHOW_ALL = os.environ.get("CHAIN_SHOW_TEST_CONTENT", "0").lower() in ("1", "true", "yes")


def is_test_profile(profile):
    if _SHOW_ALL:
        return False
    username = (profile.get("username") or "").strip().lower()
    email = (profile.get("email") or profile.get("normalized_email") or "").strip().lower()
    for pat in _TEST_USER_PATTERNS:
        if pat.search(username):
            return True
    for pat in _TEST_EMAIL_PATTERNS:
        if pat.search(email):
            return True
    if profile.get("is_test_account") is True or profile.get("is_demo_account") is True:
        return True
    if profile.get("production_visible") is False:
        return True
    return False


def filter_feed_posts(posts, profile_map=None):
    if _SHOW_ALL:
        return posts
    result = []
    for p in posts:
        pid = p.get("profile_id")
        if pid and profile_map:
            profile = profile_map.get(pid) or {}
            if is_test_profile(profile):
                continue
        username = (p.get("username") or "").strip().lower()
        if any(pat.search(username) for pat in _TEST_USER_PATTERNS):
            continue
        email = (p.get("email") or p.get("normalized_email") or "").strip().lower()
        if any(pat.search(email) for pat in _TEST_EMAIL_PATTERNS):
            continue
        result.append(p)
    return result


def filter_profiles(profiles):
    if _SHOW_ALL:
        return profiles
    return [p for p in profiles if not is_test_profile(p)]


def public_profile_sql(alias="chain_profiles"):
    """SQL condition for public profile surfaces."""
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
        f"AND LOWER(COALESCE({prefix}username, '')) NOT LIKE 'devsetup_%%' "
        f"AND LOWER(COALESCE({prefix}email, '')) NOT LIKE '%%.local' "
        f"AND LOWER(COALESCE({prefix}email, '')) NOT LIKE '%%@chain.local'"
    )


def public_profile_subquery():
    """SQL subquery for content tables with profile_id ownership."""
    return f"SELECT id FROM chain_profiles WHERE {public_profile_sql('chain_profiles')}"
