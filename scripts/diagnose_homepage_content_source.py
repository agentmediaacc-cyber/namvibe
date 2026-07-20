#!/usr/bin/env python3
"""Bounded homepage content source diagnostic.

Classifies a search phrase as coming from visible user content, a system
placeholder, embedded state, cache content, or an unresolved source.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_FAST_LOCAL", "1")

from engines.cache_engine import get_cache

CLASSIFICATION = {
    "visible": "LEGITIMATE_USER_CONTENT",
    "placeholder": "SYSTEM_PLACEHOLDER",
    "cache": "CACHED_UNKNOWN_CONTENT",
    "embedded": "EMBEDDED_NONVISIBLE_STATE",
    "unresolved": "UNRESOLVED",
}


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def _excerpt(text: str, phrase: str, radius: int = 80) -> str:
    low = text.lower()
    idx = low.find(phrase.lower())
    if idx < 0:
        return ""
    start = max(0, idx - radius)
    end = min(len(text), idx + len(phrase) + radius)
    return re.sub(r"\s+", " ", text[start:end]).strip()[:200]


def _safe_print(payload):
    print(json.dumps(payload, sort_keys=True))


def classify_html(html: str, phrase: str):
    low = html.lower()
    if phrase.lower() not in low:
        return None
    excerpt = _excerpt(html, phrase)
    tag = None
    element_id = None
    element_classes = []
    parent_classes = []
    if "data-placeholder" in low or "demo" in low or "fixture" in low or "system" in low:
        classification = CLASSIFICATION["placeholder"]
    elif "<script" in low and phrase.lower() in low:
        classification = CLASSIFICATION["embedded"]
    else:
        classification = CLASSIFICATION["visible"]
    return {
        "classification": classification,
        "source": "html",
        "tag": tag,
        "element_id": element_id,
        "element_classes": element_classes,
        "parent_classes": parent_classes,
        "content_type": "text/html",
        "safe_identifier": None,
        "creator_handle": None,
        "flags": {
            "is_demo": "demo" in low,
            "is_placeholder": "placeholder" in low,
            "is_fixture": "fixture" in low,
            "is_system": "system" in low,
        },
        "excerpt": excerpt,
        "visibility": "visible_text",
    }


def cache_search(phrase: str):
    keys = (
        "homepage:full:public",
        "homepage:full:public:stale",
        "phase51:homepage:payload",
        "phase51:homepage:payload:stale",
        "phase51:homepage:stories",
        "phase51:homepage:reels",
        "phase51:homepage:live_rooms",
        "phase51:homepage:trending_posts",
        "phase51:homepage:creator_profiles",
        "phase51:homepage:suggested_people",
    )
    for key in keys:
        try:
            value = get_cache(key)
        except Exception as exc:
            return {
                "classification": CLASSIFICATION["unresolved"],
                "source": "cache",
                "error": f"cache read failed: {exc}",
                "key": key,
            }
        if value is None:
            continue
        text = json.dumps(value, sort_keys=True, default=str)
        if phrase.lower() in text.lower():
            return {
                "classification": CLASSIFICATION["cache"],
                "source": "cache",
                "key": key,
                "content_type": "application/json",
                "safe_identifier": key,
                "visibility": "embedded_state",
                "excerpt": _excerpt(text, phrase),
            }
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", required=True, help="Phrase to classify")
    parser.add_argument("--html", help="Optional HTML file to inspect first")
    args = parser.parse_args()

    if args.html and os.path.exists(args.html):
        with open(args.html, "r", encoding="utf-8", errors="ignore") as fh:
            html = fh.read()
        result = classify_html(html, args.search)
        if result:
            _safe_print(result)
            return 0

    result = cache_search(args.search)
    if result:
        _safe_print(result)
        return 2 if result["classification"] == CLASSIFICATION["unresolved"] else 0

    _safe_print({"classification": CLASSIFICATION["unresolved"], "source": "none"})
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
