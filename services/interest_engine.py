"""Personal interest vector builder for feed ranking."""

import json
import re
import time
from datetime import datetime, timezone
from collections import defaultdict

from services.neon_service import fast_query
from services.redis_service import cache_get, cache_set

INTEREST_TTL = 3600
MAX_HASHTAGS = 50
MAX_LOCATIONS = 10
MAX_CATEGORIES = 20
DECAY_HOURS = 168

_HASHTAG_RE = re.compile(r'#(\w[\w\']*)', re.IGNORECASE)


def _utcnow():
    return datetime.now(timezone.utc)


def _extract_hashtags(text):
    if not text:
        return []
    return [t.lower() for t in _HASHTAG_RE.findall(str(text))]


def build_interest_profile(profile_id):
    if not profile_id:
        return _empty_profile()

    cache_key = f"interest:v2:{profile_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    vectors = defaultdict(float)

    _collect_liked_posts(vectors, profile_id)
    _collect_liked_reels(vectors, profile_id)
    _collect_saved_posts(vectors, profile_id)
    _collect_saved_reels(vectors, profile_id)
    _collect_shared_posts(vectors, profile_id)
    _collect_watched_reels(vectors, profile_id)
    _collect_commented_posts(vectors, profile_id)
    _collect_followed_creators(vectors, profile_id)
    _collect_search_history(vectors, profile_id)
    _collect_profile_location(vectors, profile_id)

    profile = _prune_vectors(dict(vectors))
    cache_set(cache_key, profile, ttl=INTEREST_TTL)
    return profile


def _collect_liked_posts(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT p.caption, p.content, p.category, p.town_tag, p.created_at
               FROM chain_post_reactions l
               JOIN chain_posts p ON p.id = l.post_id
               WHERE l.profile_id = %s AND l.reaction_type = 'like'
               ORDER BY l.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_post_signals(vectors, row, w * 2.0)
    except Exception:
        pass


def _collect_liked_reels(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT r.caption, r.content, r.category, r.created_at
               FROM chain_reel_reactions l
               JOIN chain_reels r ON r.id = l.reel_id
               WHERE l.profile_id = %s AND l.reaction_type = 'like'
               ORDER BY l.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_reel_signals(vectors, row, w * 2.0)
    except Exception:
        pass


def _collect_saved_posts(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT p.caption, p.content, p.category, p.town_tag, p.created_at
               FROM chain_saved_items s
               JOIN chain_posts p ON p.id = s.item_id
               WHERE s.profile_id = %s AND s.item_type = 'post'
               ORDER BY s.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_post_signals(vectors, row, w * 1.5)
    except Exception:
        pass


def _collect_saved_reels(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT r.caption, r.content, r.category, r.created_at
               FROM chain_saved_items s
               JOIN chain_reels r ON r.id = s.item_id
               WHERE s.profile_id = %s AND s.item_type = 'reel'
               ORDER BY s.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_reel_signals(vectors, row, w * 1.5)
    except Exception:
        pass


def _collect_shared_posts(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT p.caption, p.content, p.category, p.town_tag, p.created_at
               FROM chain_shares s
               JOIN chain_posts p ON p.id = s.post_id
               WHERE s.profile_id = %s AND s.deleted_at IS NULL
               ORDER BY s.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_post_signals(vectors, row, w * 1.2)
    except Exception:
        pass


def _collect_watched_reels(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT r.caption, r.content, r.category, r.created_at
               FROM chain_reel_events v
               JOIN chain_reels r ON r.id = v.reel_id
               WHERE v.user_id = %s AND v.event_type = 'view'
               ORDER BY v.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_reel_signals(vectors, row, w * 0.5)
    except Exception:
        pass


def _collect_commented_posts(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT p.caption, p.content, p.category, p.town_tag, p.created_at
               FROM chain_comments c
               JOIN chain_posts p ON p.id = c.post_id
               WHERE c.profile_id = %s AND c.deleted_at IS NULL
               ORDER BY c.created_at DESC LIMIT 200""",
            (profile_id,), default=[]
        )
        for row in rows:
            w = _recency_weight(row.get("created_at"))
            _add_post_signals(vectors, row, w * 1.0)
    except Exception:
        pass


def _collect_followed_creators(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT p.creator_category, p.current_location, p.interests
               FROM chain_follows f
               JOIN chain_profiles p ON p.id = f.following_profile_id
               WHERE f.follower_profile_id = %s AND f.deleted_at IS NULL
               ORDER BY f.created_at DESC LIMIT 100""",
            (profile_id,), default=[]
        )
        for row in rows:
            interests = row.get("interests")
            if interests:
                if isinstance(interests, list):
                    for tag in interests:
                        if isinstance(tag, str):
                            vectors[f"hashtag:{tag.lower()}"] += 1.0
                        elif isinstance(tag, dict) and "name" in tag:
                            vectors[f"hashtag:{tag['name'].lower()}"] += 1.0
                elif isinstance(interests, str):
                    for tag in _parse_tags(interests):
                        vectors[f"hashtag:{tag.lower()}"] += 1.0
            cat = (row.get("creator_category") or "").strip().lower()
            if cat:
                vectors[f"category:{cat}"] += 2.0
            loc = (row.get("current_location") or "").strip().lower()
            if loc:
                vectors[f"location:{loc}"] += 1.5
    except Exception:
        pass


def _collect_search_history(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT query FROM chain_search_history
               WHERE profile_id = %s
               ORDER BY created_at DESC LIMIT 100""",
            (profile_id,), default=[]
        )
        for row in rows:
            q = (row.get("query") or "").strip().lower()
            if q.startswith("#"):
                vectors[f"hashtag:{q[1:]}"] += 0.8
            elif q:
                vectors[f"search:{q}"] += 0.5
    except Exception:
        pass


def _collect_profile_location(vectors, profile_id):
    try:
        rows = fast_query(
            """SELECT current_location, region, country_origin, interests
               FROM chain_profiles WHERE id = %s LIMIT 1""",
            (profile_id,), default=[]
        )
        if rows:
            loc = (rows[0].get("current_location") or rows[0].get("region") or rows[0].get("country_origin") or "").strip().lower()
            if loc:
                vectors[f"location:{loc}"] += 3.0
            interests = rows[0].get("interests")
            if interests:
                if isinstance(interests, list):
                    for tag in interests:
                        if isinstance(tag, str):
                            vectors[f"hashtag:{tag.lower()}"] += 2.0
                        elif isinstance(tag, dict) and "name" in tag:
                            vectors[f"hashtag:{tag['name'].lower()}"] += 2.0
                elif isinstance(interests, str):
                    for tag in _parse_tags(interests):
                        vectors[f"hashtag:{tag.lower()}"] += 2.0
    except Exception:
        pass


def _add_post_signals(vectors, row, weight):
    for tag in _extract_hashtags(row.get("caption")):
        vectors[f"hashtag:{tag}"] += weight
    for tag in _extract_hashtags(row.get("content")):
        vectors[f"hashtag:{tag}"] += weight * 0.5
    loc = (row.get("town_tag") or "").strip().lower()
    if loc:
        vectors[f"location:{loc}"] += weight * 0.8
    cat = (row.get("category") or "").strip().lower()
    if cat:
        vectors[f"category:{cat}"] += weight


def _add_reel_signals(vectors, row, weight):
    for tag in _extract_hashtags(row.get("caption")):
        vectors[f"hashtag:{tag}"] += weight
    for tag in _extract_hashtags(row.get("content")):
        vectors[f"hashtag:{tag}"] += weight * 0.5
    cat = (row.get("category") or "").strip().lower()
    if cat:
        vectors[f"category:{cat}"] += weight


def _parse_tags(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(t).strip().lower() for t in value if t]
    if isinstance(value, str):
        return [t.strip().lower() for t in re.split(r'[,;\s]+', value) if t.strip()]
    return []


def _recency_weight(created_at):
    if not created_at:
        return 0.3
    try:
        if isinstance(created_at, str):
            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        else:
            dt = created_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        age_hours = (_utcnow() - dt).total_seconds() / 3600
        return max(0.1, 1.0 - age_hours / DECAY_HOURS)
    except Exception:
        return 0.3


def _prune_vectors(vectors):
    top_hashtags = {}
    top_locations = {}
    top_categories = {}
    top_searches = {}
    for key, value in vectors.items():
        if key.startswith("hashtag:"):
            top_hashtags[key] = value
        elif key.startswith("location:"):
            top_locations[key] = value
        elif key.startswith("category:"):
            top_categories[key] = value
        elif key.startswith("search:"):
            top_searches[key] = value

    sorted_hashtags = sorted(top_hashtags.items(), key=lambda x: -x[1])[:MAX_HASHTAGS]
    sorted_locations = sorted(top_locations.items(), key=lambda x: -x[1])[:MAX_LOCATIONS]
    sorted_categories = sorted(top_categories.items(), key=lambda x: -x[1])[:MAX_CATEGORIES]

    result = dict(sorted_hashtags)
    result.update(dict(sorted_locations))
    result.update(dict(sorted_categories))
    result.update(dict(sorted(top_searches.items(), key=lambda x: -x[1])[:20]))
    return result


def _empty_profile():
    return {}


def interest_similarity(profile_id_a, profile_id_b):
    va = build_interest_profile(profile_id_a)
    vb = build_interest_profile(profile_id_b)
    if not va or not vb:
        return 0.0
    common_keys = set(va.keys()) & set(vb.keys())
    if not common_keys:
        return 0.0
    dot = sum(va[k] * vb[k] for k in common_keys)
    norm_a = sum(v ** 2 for v in va.values()) ** 0.5
    norm_b = sum(v ** 2 for v in vb.values()) ** 0.5
    if norm_a * norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def interest_match_score(profile_id, item):
    profile = build_interest_profile(profile_id)
    if not profile:
        return 0.0

    item_tags = set()
    for tag in _extract_hashtags(item.get("caption", item.get("title", ""))):
        item_tags.add(f"hashtag:{tag}")
    item_cat = (item.get("category") or "").strip().lower()
    if item_cat:
        item_tags.add(f"category:{item_cat}")
    item_loc = (item.get("town_tag") or item.get("author_region") or item.get("location") or "").strip().lower()
    if item_loc:
        item_tags.add(f"location:{item_loc}")

    if not item_tags:
        return 0.0

    score = 0.0
    for key in item_tags:
        score += profile.get(key, 0.0)
    return score / len(item_tags)
