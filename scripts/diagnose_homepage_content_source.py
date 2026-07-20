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
from html.parser import HTMLParser

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


class _TextFinder(HTMLParser):
    def __init__(self, phrase: str):
        super().__init__()
        self.phrase = phrase.lower()
        self.match = None
        self.stack = []

    def handle_starttag(self, tag, attrs):
        attr_map = dict(attrs)
        self.stack.append(
            {
                "tag": tag,
                "id": attr_map.get("id"),
                "class": attr_map.get("class", ""),
                "attrs": attr_map,
            }
        )

    def handle_endtag(self, tag):
        while self.stack:
            item = self.stack.pop()
            if item["tag"] == tag:
                break

    def handle_data(self, data):
        if self.match or self.phrase not in data.lower():
            return
        current = self.stack[-1] if self.stack else {}
        parent = self.stack[-2] if len(self.stack) >= 2 else {}
        self.match = {
            "tag": current.get("tag"),
            "element_id": current.get("id"),
            "element_classes": current.get("class", "").split(),
            "parent_tag": parent.get("tag"),
            "parent_classes": parent.get("class", "").split(),
            "excerpt": data.strip()[:200],
        }


def classify_html(html: str, phrase: str):
    low = html.lower()
    if phrase.lower() not in low:
        return None
    excerpt = _excerpt(html, phrase)
    parser = _TextFinder(phrase)
    try:
        parser.feed(html)
    except Exception:
        parser.match = None
    match = parser.match or {}
    if "data-placeholder" in low or "demo" in low or "fixture" in low or "system" in low:
        classification = CLASSIFICATION["placeholder"]
    elif "<script" in low and phrase.lower() in low:
        classification = CLASSIFICATION["embedded"]
    else:
        classification = CLASSIFICATION["visible"]
    return {
        "classification": classification,
        "source": "html",
        "tag": match.get("tag"),
        "element_id": match.get("element_id"),
        "element_classes": match.get("element_classes", []),
        "parent_tag": match.get("parent_tag"),
        "parent_classes": match.get("parent_classes", []),
        "content_type": "text/html",
        "safe_identifier": None,
        "creator_handle": None,
        "flags": {
            "is_demo": "demo" in low,
            "is_placeholder": "placeholder" in low,
            "is_fixture": "fixture" in low,
            "is_system": "system" in low,
        },
        "excerpt": match.get("excerpt") or excerpt,
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
