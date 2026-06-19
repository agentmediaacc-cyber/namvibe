"""Production-facing filters for fake, seed, and placeholder content."""

import re
from collections.abc import Mapping


_FAKE_USERNAME_PATTERNS = (
    re.compile(r"^phase8_", re.I),
    re.compile(r"^test(user)?[_-]?", re.I),
    re.compile(r"^demo[_-]", re.I),
    re.compile(r"^dev(setup)?[_-]", re.I),
    re.compile(r".*seed.*", re.I),
)

_FAKE_TEXT_PATTERNS = (
    re.compile(r"phase\s*8", re.I),
    re.compile(r"phase8", re.I),
    re.compile(r"production\s+reel", re.I),
    re.compile(r"production\s+post", re.I),
    re.compile(r"test\s+(post|reel|story|user|content)", re.I),
    re.compile(r"\blorem\b|\bipsum\b", re.I),
    re.compile(r"\bdummy\b|\bfake\b|\bsample\b", re.I),
    re.compile(r"\bseed(ed)?\b", re.I),
    re.compile(r"\bTODO\b", re.I),
    re.compile(r"\bhardcoded\b", re.I),
)

_PLACEHOLDER_ONLY_PATTERNS = (
    re.compile(r"^\s*(coming soon|placeholder|todo|n/a|none|null)\s*$", re.I),
    re.compile(r"^\s*(lorem ipsum|dummy|fake|sample|seed)\b", re.I),
)


def _value(row, key):
    if isinstance(row, Mapping):
        return row.get(key)
    return getattr(row, key, None)


def _stringify(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(_stringify(item) for item in value)
    if isinstance(value, Mapping):
        return " ".join(_stringify(item) for item in value.values())
    return str(value)


def should_hide_placeholder(value):
    """Return True when a public text value is only fake/placeholder copy."""
    text = _stringify(value).strip()
    if not text:
        return False
    return any(pattern.search(text) for pattern in _PLACEHOLDER_ONLY_PATTERNS)


def clean_text_for_public(text):
    """Blank fake placeholder copy before rendering it in public surfaces."""
    if should_hide_placeholder(text):
        return ""
    value = _stringify(text).strip()
    if any(pattern.search(value) for pattern in _FAKE_TEXT_PATTERNS):
        return ""
    return value


def is_fake_content(row):
    """Detect obvious seed/test rows before they reach public pages."""
    if not row:
        return False

    username = _stringify(
        _value(row, "username")
        or _value(row, "p_username")
        or _value(row, "handle")
    ).strip()
    if any(pattern.search(username) for pattern in _FAKE_USERNAME_PATTERNS):
        return True

    marker_values = (
        _value(row, "is_test_account"),
        _value(row, "is_demo_account"),
        _value(row, "seed_marker"),
        _value(row, "test_marker"),
    )
    if any(value is True or _stringify(value).lower() in {"1", "true", "yes"} for value in marker_values):
        return True

    text_fields = (
        "caption",
        "body",
        "content",
        "text",
        "title",
        "description",
        "display_name",
        "hashtags",
        "music_title",
        "sound_title",
        "sound",
    )
    haystack = " ".join(_stringify(_value(row, field)) for field in text_fields)
    if any(pattern.search(haystack) for pattern in _FAKE_TEXT_PATTERNS):
        return True

    if re.search(r"original\s+sound", haystack, re.I) and re.search(r"phase8|phase\s*8|test|seed", haystack, re.I):
        return True

    email = _stringify(_value(row, "email") or _value(row, "normalized_email")).strip().lower()
    if email.endswith(".local") or email.endswith("@chain.local"):
        return True

    return False


def filter_fake_content(rows):
    """Return only production-safe mapping rows."""
    return [row for row in rows or [] if not is_fake_content(row)]
