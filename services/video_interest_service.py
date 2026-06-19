"""Lightweight video-interest tracking and personalized reel ranking."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from typing import Dict, Iterable, List, Optional

from engines.cache_engine import cache_key, get_cache, set_cache
from services.homepage_real_data_guard import filter_content
from services.neon_service import fast_query, write_query
from services.production_content_guard import is_fake_content
from services.relationship_privacy_service import can_view_reels, is_blocked_any


POSITIVE_WEIGHTS = {
    "impression": 0.2,
    "view": 1.0,
    "watch_3s": 2.5,
    "watch_10s": 5.0,
    "complete": 8.0,
    "like": 6.0,
    "comment": 8.0,
    "share": 9.0,
    "save": 10.0,
    "follow_creator": 12.0,
}
NEGATIVE_WEIGHTS = {"skip": -6.0}
VIDEO_EVENT_TTL_SECONDS = 30


def record_video_event(
    viewer_profile_id,
    video_type,
    video_id,
    creator_profile_id=None,
    event_type="view",
    watch_ms=0,
):
    if not viewer_profile_id or not video_id:
        return {"ok": False, "error": "missing_required_fields"}
    event_type = event_type if event_type in set(POSITIVE_WEIGHTS) | set(NEGATIVE_WEIGHTS) else "view"
    video_type = video_type if video_type in {"reel", "post", "story"} else "reel"
    payload = {
        "id": str(uuid.uuid4()),
        "viewer_profile_id": str(viewer_profile_id),
        "video_type": video_type,
        "video_id": str(video_id),
        "creator_profile_id": str(creator_profile_id) if creator_profile_id else None,
        "event_type": event_type,
        "watch_ms": int(watch_ms or 0),
    }
    try:
        write_query(
            """
            INSERT INTO chain_video_events
              (id, viewer_profile_id, video_type, video_id, creator_profile_id, event_type, watch_ms, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, now())
            """,
            (
                payload["id"],
                payload["viewer_profile_id"],
                payload["video_type"],
                payload["video_id"],
                payload["creator_profile_id"],
                payload["event_type"],
                payload["watch_ms"],
            ),
            timeout_ms=700,
        )
    except Exception as error:
        return {"ok": False, "queued": False, "error": str(error)}
    return {"ok": True, "event": payload}


def _viewer_interest_profile(viewer_profile_id) -> Dict:
    rows = fast_query(
        """
        SELECT video_id::text, creator_profile_id::text, event_type, COALESCE(watch_ms, 0) AS watch_ms
        FROM chain_video_events
        WHERE viewer_profile_id = %s
          AND created_at > now() - interval '30 days'
        ORDER BY created_at DESC
        LIMIT 500
        """,
        (viewer_profile_id,),
        timeout_ms=700,
        default=[],
    )
    video_scores = Counter()
    creator_scores = Counter()
    skipped = set()
    for row in rows:
        event = row.get("event_type")
        weight = POSITIVE_WEIGHTS.get(event, NEGATIVE_WEIGHTS.get(event, 0))
        weight += min(int(row.get("watch_ms") or 0), 120000) / 30000.0
        vid = str(row.get("video_id") or "")
        creator = str(row.get("creator_profile_id") or "")
        if event == "skip":
            skipped.add(vid)
        if vid:
            video_scores[vid] += weight
        if creator:
            creator_scores[creator] += weight
    return {"video_scores": video_scores, "creator_scores": creator_scores, "skipped": skipped}


def _fallback_reels(limit: int) -> List[Dict]:
    try:
        from services.reels_service import get_reel_feed
        return filter_content(get_reel_feed(limit=limit))
    except Exception:
        return []


def rank_reels_for_viewer(viewer_profile_id=None, reels: Optional[Iterable[Dict]] = None, limit: int = 20) -> List[Dict]:
    limit = min(max(int(limit or 20), 1), 50)
    key = cache_key("for_you_reels_v1", viewer_profile_id or "anon", str(limit))
    cached = get_cache(key)
    if isinstance(cached, list):
        return cached

    items = list(reels or _fallback_reels(max(limit * 2, 30)))
    items = filter_content(items)
    interest = _viewer_interest_profile(viewer_profile_id) if viewer_profile_id else {"video_scores": {}, "creator_scores": {}, "skipped": set()}
    ranked = []
    for item in items:
        if is_fake_content(item):
            continue
        owner_id = item.get("profile_id") or item.get("creator_profile_id")
        if viewer_profile_id and owner_id:
            if str(owner_id) == str(viewer_profile_id):
                continue
            if is_blocked_any(viewer_profile_id, owner_id):
                continue
            if not can_view_reels(viewer_profile_id, {"id": owner_id, "profile_visibility": item.get("profile_visibility") or "public"}):
                continue
        video_id = str(item.get("id") or "")
        creator_id = str(owner_id or "")
        base = (
            float(item.get("views_count") or 0) * 0.01
            + float(item.get("likes_count") or 0) * 0.25
            + float(item.get("comments_count") or 0) * 0.5
            + float(item.get("shares_count") or 0) * 0.75
        )
        score = base + interest["video_scores"].get(video_id, 0) + interest["creator_scores"].get(creator_id, 0)
        if video_id in interest["skipped"]:
            score -= 8
        enriched = dict(item)
        enriched["ranking_score"] = round(score, 2)
        ranked.append(enriched)
    ranked.sort(key=lambda row: row.get("ranking_score", 0), reverse=True)
    result = ranked[:limit]
    set_cache(key, result, ttl=VIDEO_EVENT_TTL_SECONDS)
    return result
