import copy
import time
import threading
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import has_request_context, session

from engines.cache_engine import cache_key, get_cache, set_cache
from services.request_cache import build_request_key, request_memoize
from services.neon_service import (
    fetch_all,
    fast_query,
    get_cached_table_columns,
    get_pool_status,
    get_tables_columns,
    is_circuit_open,
    safe_row_get,
)
from services.homepage_cache_service import (
    HOMEPAGE_TTL_SECONDS,
    get_full,
    get_payload,
    remember_section,
    set_full,
    set_payload,
)
from services.query_optimizer import HOMEPAGE_QUERY_BUDGET_MS, batch_load_profiles, profiled_query
from services.logging_service import log_info
from services.profile_service import get_current_profile
from services.wallet_service import ensure_wallet
from services.content_service import local_content, active_local_stories
from services.homepage_real_data_guard import filter_content, filter_profiles, public_profile_sql, public_profile_subquery


_CACHE_TTL_SECONDS = HOMEPAGE_TTL_SECONDS
_EMPTY_CACHE_TTL_SECONDS = 300
_QUERY_TIMEOUT_MS = 1500
_TOTAL_BUDGET_MS = 800
_FAST_FALLBACK_MS = 800
_SLOW_QUERY_MS = 100
_WARM_CACHE_BUDGET_MS = 1000
_HOMEPAGE_LIMITS = {
    "stories": 20,
    "reels": 20,
    "trending_posts": 20,
    "recommended_profiles": 10,
    "live_rooms": 10,
}
_HOMEPAGE_SECTION_TTLS = {
    "stories": 60,
    "reels": 60,
    "trending_posts": 120,
    "creator_profiles": 120,
    "live_rooms": 30,
    "popular_towns": 600,
    "suggested_people": 300,
    "wallet": 30,
    "notifications_unread": 15,
}
_HOMEPAGE_TABLES = [
    "chain_profiles",
    "chain_posts",
    "chain_stories",
    "chain_status_posts",
    "chain_reels",
    "chain_live_rooms",
]
_SCHEMA_CACHE = {}
_SCHEMA_LOCK = threading.Lock()
_OUTAGE_LOG = {"expires_at": 0.0}
_EXECUTOR = ThreadPoolExecutor(max_workers=10)
_SHARED_FEED_CACHE_PREFIX = "chain_homepage_feed_v1"
_TIMING_ROOT = threading.local()
_PERF_LOCAL = threading.local()
_PERF_LOCK = threading.RLock()


def _new_perf_profile():
    return {
        "homepage_start": None,
        "sections": {},
        "query_counts": Counter(),
        "slowest_query": None,
        "slowest_queries": [],
        "slowest_section": None,
        "section_cache_hits": {},
        "cache_lookup_ms": 0.0,
        "cache_store_ms": 0.0,
        "homepage_total_ms": 0.0,
    }


def reset_homepage_performance_profile():
    _PERF_LOCAL.profile = _new_perf_profile()
    _PERF_LOCAL.profile["homepage_start"] = time.perf_counter()
    return _PERF_LOCAL.profile


def get_homepage_performance_profile():
    profile = getattr(_PERF_LOCAL, "profile", None) or _new_perf_profile()
    result = copy.deepcopy(profile)
    result["query_counts"] = dict(profile.get("query_counts") or {})
    result["profile_queries"] = result["query_counts"].get("profiles", 0)
    result["post_queries"] = result["query_counts"].get("posts", 0)
    result["reel_queries"] = result["query_counts"].get("reels", 0)
    result["story_queries"] = result["query_counts"].get("stories", 0) + result["query_counts"].get("status_posts", 0)
    return result


def _perf_profile():
    profile = getattr(_PERF_LOCAL, "profile", None)
    if profile is None:
        profile = reset_homepage_performance_profile()
    return profile


def _query_bucket(label):
    label = str(label or "query")
    if label.startswith("profiles"):
        return "profiles"
    if label.startswith("posts"):
        return "posts"
    if label.startswith("reels"):
        return "reels"
    if label.startswith("stories"):
        return "stories"
    if label.startswith("status_posts"):
        return "status_posts"
    if label.startswith("live_rooms"):
        return "live_rooms"
    return label.split(":", 1)[0]


def _record_query_count(label):
    with _PERF_LOCK:
        _perf_profile()["query_counts"][_query_bucket(label)] += 1


def _record_section(section, duration_ms):
    section_name = str(section or "unknown")
    duration = round(float(duration_ms or 0), 2)
    profile = _perf_profile()
    with _PERF_LOCK:
        profile["sections"][section_name] = round(float(profile["sections"].get(section_name, 0.0) or 0.0) + duration, 2)
        if not profile.get("slowest_section") or duration > profile["slowest_section"].get("duration_ms", 0):
            profile["slowest_section"] = {"section": section_name, "duration_ms": duration}
    log_info("homepage_section_profile", section=section_name, duration_ms=duration)


def _record_cache_timing(kind, duration_ms):
    key = "cache_store_ms" if kind == "store" else "cache_lookup_ms"
    profile = _perf_profile()
    with _PERF_LOCK:
        profile[key] = round(float(profile.get(key, 0.0) or 0.0) + float(duration_ms or 0.0), 2)


def _record_section_cache_hit(section, cache_hit):
    with _PERF_LOCK:
        _perf_profile()["section_cache_hits"][section] = bool(cache_hit)


def _record_homepage_total(duration_ms):
    with _PERF_LOCK:
        _perf_profile()["homepage_total_ms"] = round(float(duration_ms or 0), 2)


def _record_query_timing(entry):
    profile = _perf_profile()
    with _PERF_LOCK:
        slowest = profile.get("slowest_query")
        if not slowest or entry["latency_ms"] > slowest.get("latency_ms", 0):
            profile["slowest_query"] = entry
        slowest_queries = list(profile.get("slowest_queries") or [])
        slowest_queries.append(entry)
        slowest_queries.sort(key=lambda item: item.get("latency_ms", 0), reverse=True)
        profile["slowest_queries"] = slowest_queries[:5]
    if entry.get("latency_ms", 0) > _SLOW_QUERY_MS:
        log_info(
            "homepage_slow_query",
            label=entry.get("label"),
            latency_ms=entry.get("latency_ms"),
            row_count=entry.get("row_count"),
            threshold_ms=_SLOW_QUERY_MS,
            recommended_fix=_recommended_query_fix(entry.get("label")),
        )


def _recommended_query_fix(label):
    bucket = _query_bucket(label)
    if bucket in {"stories", "status_posts"}:
        return "Use partial index on story/status created_at for active, non-deleted rows."
    if bucket == "reels":
        return "Use partial index on chain_reels(created_at DESC) WHERE deleted_at IS NULL."
    if bucket == "posts":
        return "Use partial index on chain_posts(created_at DESC) WHERE deleted_at IS NULL."
    if bucket == "profiles":
        return "Use partial index on chain_profiles(created_at DESC) or followers_count for visible creator rows."
    if bucket == "live_rooms":
        return "Use partial index on chain_live_rooms(created_at DESC) WHERE deleted_at IS NULL AND is_live = TRUE."
    return "Check EXPLAIN ANALYZE and add a matching partial index for filter plus ORDER BY."


def _cap_homepage_sections(payload):
    for section, limit in _HOMEPAGE_LIMITS.items():
        values = payload.get(section)
        if isinstance(values, list):
            payload[section] = values[:limit]
    return payload


def _cache_hit_ratio(section_cache_hits):
    if not section_cache_hits:
        return 0.0
    hits = sum(1 for value in section_cache_hits.values() if value)
    return round(hits / max(len(section_cache_hits), 1), 3)


def _profiled_homepage_query(label, sql_text, params=None, timeout_ms=1000, default=None, budget_ms=None):
    from services.query_optimizer import record_query

    _record_query_count(label)
    started = time.perf_counter()
    rows = fast_query(sql_text, params=params or [], timeout_ms=timeout_ms, default=default if default is not None else [])
    latency_ms = (time.perf_counter() - started) * 1000
    count = len(rows) if isinstance(rows, list) else (1 if rows else 0)
    entry = record_query(sql_text, latency_ms, count, label=label, budget_ms=budget_ms)
    entry.setdefault("label", label)
    entry.setdefault("latency_ms", round(latency_ms, 2))
    entry.setdefault("row_count", count)
    _record_query_timing(entry)
    return rows


def _log(message):
    print(f"[homepage_service] {message}")


def _timing_origin():
    return getattr(_TIMING_ROOT, "started_at", None) or time.perf_counter()


def _log_section_timing(section_name, start, end=None):
    end = end or time.perf_counter()
    origin = _timing_origin()
    log_info(
        "homepage_section_timing",
        section_name=section_name,
        start_ms=round((start - origin) * 1000, 2),
        end_ms=round((end - origin) * 1000, 2),
        duration_ms=round((end - start) * 1000, 2),
    )


def _fast_local_enabled():
    return os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production"


def _empty_homepage_payload(issue=None):
    issues = [issue] if issue else []
    return {
        "stories": [],
        "live_rooms": [],
        "recommended_profiles": [],
        "trending_posts": [],
        "dating_matches": [],
        "reels": [],
        "stats": {"stories": 0, "live_rooms": 0, "profiles": 0, "posts": 0, "reels": 0},
        "issues": issues,
    }


def _log_outage_once(message):
    now = time.monotonic()
    if _OUTAGE_LOG["expires_at"] > now:
        return
    _OUTAGE_LOG["expires_at"] = now + 60
    _log(message)


def _utcnow():
    return datetime.now(timezone.utc)


def _now_ts():
    return time.monotonic()


def _clean_text(value, fallback=""):
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _safe_int(value, default=0):
    try:
        if value in (None, "", False):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value, default=0.0):
    try:
        if value in (None, "", False):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _boolish(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return value != 0
    return str(value).strip().lower() in {"1", "true", "yes", "on", "live", "active", "online", "verified"}


def _first_present(record, keys, default=None):
    if not isinstance(record, dict):
        return default
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def _format_relative(value):
    if not value:
        return "Just now"
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value).strip()
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return raw[:16].replace("T", " ")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = _utcnow() - parsed.astimezone(timezone.utc)
    seconds = max(int(delta.total_seconds()), 0)
    if seconds < 60:
        return "Just now"
    if seconds < 3600:
        return f"{seconds // 60}m ago"
    if seconds < 86400:
        return f"{seconds // 3600}h ago"
    if seconds < 604800:
        return f"{seconds // 86400}d ago"
    return parsed.strftime("%d %b")


def _table_columns(table_name):
    global _SCHEMA_CACHE
    now = time.monotonic()
    
    # 1. Quick cache check (no lock)
    if _SCHEMA_CACHE and _SCHEMA_CACHE.get("_expires_at", 0) > now:
        _log(f"schema_cache_hit table={table_name} kind=columns")
        return _SCHEMA_CACHE.get(table_name, set())

    # 2. Lock for lookup
    with _SCHEMA_LOCK:
        # Re-check cache
        if _SCHEMA_CACHE and _SCHEMA_CACHE.get("_expires_at", 0) > now:
            _log(f"schema_cache_hit table={table_name} kind=columns")
            return _SCHEMA_CACHE.get(table_name, set())

        _log(f"schema_cache_miss table={table_name} kind=columns")
        if _fast_local_enabled():
            _log(f"schema_check_skipped_fast_local table={table_name} kind=columns")
            _SCHEMA_CACHE = {"_expires_at": now + 600}
            return set()

        # Initialize or refresh
        new_cache = {"_expires_at": now + 600} # Cache schema for at least 10 mins in dev
        
        try:
            # Try local memory/filesystem cache first
            for name in _HOMEPAGE_TABLES:
                cached_columns = get_cached_table_columns(name)
                if cached_columns:
                    new_cache[name] = set(cached_columns)
            
            # If missing anything, try a quick DB lookup
            if len(new_cache) < len(_HOMEPAGE_TABLES) + 1: # +1 for _expires_at
                db_schemas = get_tables_columns(_HOMEPAGE_TABLES, timeout_ms=1000)
                for name, columns in db_schemas.items():
                    new_cache[name] = set(columns)
        except Exception as e:
            _log(f"Schema lookup failed: {e}")
            # If it failed, don't try again immediately (30s backoff)
            new_cache["_expires_at"] = now + 30
        
        _SCHEMA_CACHE = new_cache
        return _SCHEMA_CACHE.get(table_name, set())


def _select_columns(table_name, candidates, required=None):
    available = _table_columns(table_name)
    if not available:
        # If schema lookup failed, skip table if it's reels or stories, or use minimal for profiles/posts
        if table_name in {"chain_reels", "chain_stories", "chain_status_posts"}:
            return []
        return [c for c in candidates if c in {"id", "created_at", "username", "display_name", "profile_id"}]
    
    if required and any(column not in available for column in required):
        return []
    return [column for column in candidates if column in available]


def _run_sql(query_key, sql_text, params=None, timeout_ms=_QUERY_TIMEOUT_MS):
    rows = request_memoize(
        build_request_key("homepage_sql", query_key, sql_text, tuple(params or [])),
        lambda: _profiled_homepage_query(
            query_key,
            sql_text,
            params=params or [],
            timeout_ms=timeout_ms,
            default=[],
            budget_ms=HOMEPAGE_QUERY_BUDGET_MS.get(query_key.split(":")[0]),
        ),
    )
    issue = f"{query_key}: unavailable" if not rows and get_pool_status().get("backoff_active") else None
    return rows, issue


def _profile_select():
    return _select_columns(
        "chain_profiles",
        [
            "id",
            "username",
            "display_name",
            "full_name",
            "avatar_url",
            "photo_url",
            "thumbnail_url",
            "town",
            "location",
            "bio",
            "created_at",
            "is_verified",
            "verified",
            "is_online",
            "is_creator",
            "creator_category",
            "dating_mode_enabled",
            "followers_count",
            "deleted_at",
        ],
        required=["id"],
    )


def _post_select():
    return _select_columns(
        "chain_posts",
        [
            "id",
            "profile_id",
            "caption",
            "content",
            "body",
            "media_url",
            "video_url",
            "thumbnail_url",
            "link_url",
            "town_tag",
            "visibility",
            "post_type",
            "likes_count",
            "comments_count",
            "created_at",
            "category",
            "deleted_at",
        ],
        required=["id"],
    )


def _story_select():
    return _select_columns(
        "chain_stories",
        [
            "id",
            "profile_id",
            "caption",
            "media_url",
            "video_url",
            "thumbnail_url",
            "visibility",
            "created_at",
            "status",
            "active",
            "is_active",
            "deleted_at",
        ],
        required=["id"],
    )


def _status_select():
    return _select_columns(
        "chain_status_posts",
        [
            "id",
            "profile_id",
            "caption",
            "media_url",
            "video_url",
            "thumbnail_url",
            "created_at",
            "expires_at",
            "status",
            "deleted_at",
        ],
        required=["id"],
    )


def _reel_select():
    return _select_columns(
        "chain_reels",
        [
            "id",
            "profile_id",
            "caption",
            "video_url",
            "thumbnail_url",
            "media_url",
            "created_at",
            "deleted_at",
        ],
        required=["id"],
    )


def _live_select():
    return _select_columns(
        "chain_live_rooms",
        [
            "id",
            "profile_id",
            "host_id",
            "creator_id",
            "title",
            "room_title",
            "category",
            "status",
            "is_live",
            "viewer_count",
            "viewers",
            "cover_url",
            "thumbnail_url",
            "media_url",
            "entry_fee",
            "coins_required",
            "created_at",
            "deleted_at",
        ],
        required=["id"],
    )


def _build_where(columns, extra=None):
    clauses = []
    if "deleted_at" in columns:
        clauses.append("deleted_at IS NULL")
    if extra:
        clauses.extend(extra)
    return clauses


def _fetch_profiles(limit=10, only_creators=False, dating_only=False):
    limit = min(int(limit or 10), _HOMEPAGE_LIMITS["recommended_profiles"])
    columns = _profile_select()
    if not columns:
        return [], ["profiles: unavailable"]
    filters = []
    available = set(columns)
    if only_creators and "is_creator" in available:
        filters.append("is_creator = TRUE")
    if dating_only:
        if "dating_mode_enabled" not in available:
            return [], ["matches: unavailable"]
        filters.append("dating_mode_enabled = TRUE")
    where = _build_where(available, filters)
    query = f"SELECT {', '.join(columns)} FROM chain_profiles"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    order_column = "created_at" if "created_at" in available else "id"
    query += f" ORDER BY {order_column} DESC LIMIT %s"
    rows, issue = _run_sql(f"profiles:{limit}:{only_creators}:{dating_only}", query, [limit])
    return rows, [issue] if issue else []


def _fetch_posts():
    columns = _post_select()
    if not columns:
        return [], ["posts: unavailable"]
    available = set(columns)
    where = _build_where(available)
    query = f"SELECT {', '.join(columns)} FROM chain_posts"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    query += " ORDER BY created_at DESC NULLS LAST"
    query += " LIMIT %s"
    rows, issue = _run_sql("posts", query, [_HOMEPAGE_LIMITS["trending_posts"]])
    return rows, [issue] if issue else []


def _fetch_stories():
    issues = []
    story_rows = []
    story_columns = _story_select()
    if story_columns:
        available = set(story_columns)
        where = _build_where(available)
        if "is_active" in available:
            where.append("is_active = TRUE")
        elif "active" in available:
            where.append("active = TRUE")
        elif "status" in available:
            where.append("COALESCE(status, '') <> 'deleted'")
        query = f"SELECT {', '.join(story_columns)} FROM chain_stories"
        if where:
            query += f" WHERE {' AND '.join(where)}"
        query += " ORDER BY created_at DESC NULLS LAST LIMIT %s"
        story_rows, issue = _run_sql("stories", query, [_HOMEPAGE_LIMITS["stories"]])
        if issue:
            issues.append(issue)
    else:
        issues.append("stories: unavailable")

    status_rows = []
    status_columns = _status_select()
    if status_columns:
        available = set(status_columns)
        cutoff = _utcnow() - timedelta(hours=24)
        where = _build_where(available, ["created_at >= %s"])
        params = [cutoff]
        if "expires_at" in available:
            where.append("(expires_at IS NULL OR expires_at > %s)")
            params.append(_utcnow())
        if "status" in available:
            where.append("COALESCE(status, '') <> 'deleted'")
        query = f"SELECT {', '.join(status_columns)} FROM chain_status_posts WHERE {' AND '.join(where)} ORDER BY created_at DESC NULLS LAST LIMIT %s"
        params.append(_HOMEPAGE_LIMITS["stories"])
        status_rows, issue = _run_sql("status_posts", query, params)
        if issue:
            issues.append(issue)

    combined = [row for row in story_rows if row.get("id")]
    for row in status_rows:
        if row.get("id"):
            combined.append(row)
    combined.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return combined[:_HOMEPAGE_LIMITS["stories"]], issues


def _fetch_reels():
    columns = _reel_select()
    if not columns:
        return [], ["reels: unavailable"]
    available = set(columns)
    where = _build_where(available)
    query = f"SELECT {', '.join(columns)} FROM chain_reels"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    query += " ORDER BY created_at DESC NULLS LAST LIMIT %s"
    rows, issue = _run_sql("reels", query, [_HOMEPAGE_LIMITS["reels"]])
    return rows, [issue] if issue else []


def _fetch_live_rooms():
    columns = _live_select()
    if not columns:
        return [], ["live_rooms: unavailable"]
    available = set(columns)
    where = _build_where(available)
    if "is_live" in available:
        where.append("is_live = TRUE")
    elif "status" in available:
        where.append("LOWER(COALESCE(status, '')) = 'live'")
    query = f"SELECT {', '.join(columns)} FROM chain_live_rooms"
    if where:
        query += f" WHERE {' AND '.join(where)}"
    query += " ORDER BY created_at DESC NULLS LAST LIMIT %s"
    rows, issue = _run_sql("live_rooms", query, [_HOMEPAGE_LIMITS["live_rooms"]])
    live_only = [row for row in rows if _boolish(row.get("is_live")) or _clean_text(row.get("status")).lower() == "live"]
    return live_only[:_HOMEPAGE_LIMITS["live_rooms"]], [issue] if issue else []


_PROFILE_JOIN_COLS = [
    "p.username AS p_username",
    "p.display_name AS p_display_name",
    "p.avatar_url AS p_avatar_url",
    "p.is_verified AS p_is_verified",
    "p.verified AS p_verified",
    "p.is_online AS p_online",
    "p.town AS p_town",
    "p.location AS p_location",
    "p.followers_count AS p_followers_count",
]

def _profile_from_row(row):
    if not row or not row.get("p_username"):
        return {}
    return {
        "display_name": row.get("p_display_name") or row.get("p_username") or "",
        "username": row.get("p_username") or "",
        "avatar_url": row.get("p_avatar_url") or "",
        "verified": row.get("p_is_verified", False) or row.get("p_verified", False),
        "is_online": row.get("p_online", False),
        "town": row.get("p_town") or "",
        "location": row.get("p_location") or "",
        "followers_count": row.get("p_followers_count", 0) or 0,
        "profile_url": f"/profile/@{row.get('p_username')}" if row.get("p_username") else "/discover/",
        "message_url": "/messages/" if row.get("p_username") else "/discover/",
        "initial": (row.get("p_display_name") or row.get("p_username") or "?")[:1].upper(),
    }


def _load_profile_map(profile_ids):
    started = time.perf_counter()
    columns = _profile_select()
    if not profile_ids or not columns:
        _log_section_timing("_load_profile_map", started)
        _record_section("profiles", (time.perf_counter() - started) * 1000)
        return {}
    _record_query_count("profiles")
    result = batch_load_profiles(profile_ids, columns, _build_where, _normalize_profile, timeout_ms=200)
    _log_section_timing("_load_profile_map", started)
    _record_section("profiles", (time.perf_counter() - started) * 1000)
    return result


def _normalize_profile(row):
    if row and not isinstance(row, dict):
        return None
    if not row:
        return None
    username = _clean_text(row.get("username"))
    display_name = _clean_text(_first_present(row, ["display_name", "full_name", "username"]), "")
    avatar_url = _first_present(row, ["avatar_url", "photo_url", "media_url", "thumbnail_url"])
    town = _clean_text(_first_present(row, ["town", "city", "location", "current_location"]), "")
    region = _clean_text(_first_present(row, ["region", "country", "country_origin"]), "")
    location = ", ".join(part for part in [town, region] if part)
    profile_id = _first_present(row, ["id", "auth_user_id"])
    return {
        "id": profile_id,
        "username": username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "verified": _boolish(_first_present(row, ["verified", "is_verified"])),
        "is_online": _boolish(row.get("is_online")),
        "location": location,
        "town": town,
        "creator_category": _clean_text(row.get("creator_category"), ""),
        "dating_mode_enabled": _boolish(row.get("dating_mode_enabled")),
        "created_label": _format_relative(row.get("created_at")),
        "initial": (display_name or username or "?")[:1].upper(),
        "profile_url": f"/profile/@{username}" if username else "/discover/",
        "message_url": "/messages/" if username else "/discover/",
    }


def _normalize_story(row, profile_map):
    if row and not isinstance(row, dict):
        return {}
    profile = profile_map.get(row.get("profile_id"))
    if profile is None:
        profile = _profile_from_row(row)
    if not profile:
        profile = {}
    display_name = profile.get("display_name") or profile.get("username") or ""
    return {
        "id": row.get("id"),
        "display_name": display_name,
        "avatar_url": profile.get("avatar_url"),
        "verified": profile.get("verified", False),
        "is_online": profile.get("is_online", False),
        "caption": _clean_text(row.get("caption")),
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": profile.get("profile_url", "/discover/"),
        "media_url": _first_present(row, ["media_url", "thumbnail_url"]),
        "video_url": _first_present(row, ["video_url"]),
        "thumbnail_url": _first_present(row, ["thumbnail_url", "media_url"]),
    }


def _normalize_live_room(row, profile_map):
    if row and not isinstance(row, dict):
        return {}
    profile_id = _first_present(row, ["profile_id", "host_id", "creator_id"])
    profile = profile_map.get(profile_id)
    if profile is None:
        profile = _profile_from_row(row)
    if not profile:
        profile = {}
    title = _clean_text(_first_present(row, ["title", "room_title"]), "")
    viewers = _first_present(row, ["viewer_count", "viewers"])
    fee_raw = _first_present(row, ["entry_fee", "coins_required"])
    entry_fee = _safe_float(fee_raw, 0) if fee_raw not in (None, "", False) else None
    creator_name = profile.get("display_name") or profile.get("username") or ""
    return {
        "id": row.get("id"),
        "title": title,
        "category": _clean_text(row.get("category"), ""),
        "viewer_count": _safe_int(viewers, 0) if viewers is not None else None,
        "entry_fee_label": f"{int(entry_fee)} coins" if entry_fee is not None else "",
        "cover_url": _first_present(row, ["cover_url", "thumbnail_url", "media_url"]),
        "creator_name": creator_name,
        "creator_avatar": profile.get("avatar_url"),
        "creator_verified": profile.get("verified", False),
        "creator_location": profile.get("town") or profile.get("location") or "",
        "created_label": _format_relative(row.get("created_at")),
        "watch_url": "/live/",
    }


def _normalize_post(row, profile_map):
    if row and not isinstance(row, dict):
        return {}
    profile = profile_map.get(row.get("profile_id"))
    if profile is None:
        profile = _profile_from_row(row)
    if not profile:
        profile = {}
    caption = _clean_text(_first_present(row, ["caption", "content", "body"]), "")
    return {
        "id": row.get("id"),
        "display_name": profile.get("display_name") or profile.get("username") or "",
        "username": profile.get("username", ""),
        "avatar_url": profile.get("avatar_url"),
        "verified": profile.get("verified", False),
        "caption": caption,
        "excerpt": caption[:180] + ("..." if len(caption) > 180 else ""),
        "media_url": _first_present(row, ["media_url", "thumbnail_url", "video_url"]),
        "video_url": _first_present(row, ["video_url"]),
        "link_url": _clean_text(row.get("link_url"), ""),
        "town_tag": _clean_text(row.get("town_tag"), ""),
        "visibility": _clean_text(row.get("visibility"), "public"),
        "post_type": _clean_text(row.get("post_type"), ""),
        "likes_count": _safe_int(row.get("likes_count"), 0),
        "comments_count": _safe_int(row.get("comments_count"), 0),
        "category": _clean_text(row.get("category"), ""),
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": profile.get("profile_url", "/discover/"),
    }


def _wallet_snapshot(current):
    snapshot = {"coin_balance": 0, "gift_earnings": 0, "label_balance": "0"}
    if not current or not current.get("id"):
        return snapshot
    if current.get("profile_fallback") or os.getenv("FLASK_TESTING") == "1" or (os.getenv("CHAIN_FAST_LOCAL") == "1" and os.getenv("FLASK_ENV", "development") != "production"):
        return snapshot
    try:
        wallet = ensure_wallet(current["id"]) or {}
        snapshot["coin_balance"] = _safe_int(wallet.get("coin_balance"), 0)
        snapshot["gift_earnings"] = _safe_int(wallet.get("gift_earnings"), 0)
        snapshot["label_balance"] = f"{snapshot['coin_balance']:,}"
    except Exception as error:
        _log(f"wallet unavailable: {error}")
    return snapshot


def _safe_current_profile():
    if not has_request_context():
        return None
    try:
        auth_user_id = session.get("auth_user_id")
        if auth_user_id:
            email = session.get("auth_email") or ""
            username = session.get("username") or (email.split("@")[0] if "@" in email else "chainuser")
            full_name = session.get("full_name") or username.replace("_", " ").title()
            profile_id = session.get("profile_id")
            base = {
                "id": profile_id,
                "auth_user_id": auth_user_id,
                "email": email,
                "username": username,
                "full_name": full_name,
                "display_name": full_name,
                "avatar_url": session.get("avatar_url"),
                "profile_completed": bool(session.get("profile_completed")),
                "is_verified": session.get("is_verified", False),
                "is_online": True,
            }
            if profile_id:
                try:
                    from services.profile_service import get_profile_stats
                    stats = get_profile_stats(profile_id)
                    base["followers_count"] = stats.get("followers", 0)
                    base["following_count"] = stats.get("following", 0)
                    base["post_count"] = stats.get("posts", 0)
                except Exception:
                    base["followers_count"] = 0
                    base["following_count"] = 0
                    base["post_count"] = 0
                try:
                    cache_key_w = cache_key("wallet_balance", profile_id)
                    wallet_bal = get_cache(cache_key_w)
                    if wallet_bal is None:
                        from services.wallet_service import ensure_wallet
                        wallet = ensure_wallet(profile_id)
                        wallet_bal = wallet.get("coin_balance", 0)
                        set_cache(cache_key_w, wallet_bal, ttl=30)
                    base["wallet_balance"] = wallet_bal
                except Exception:
                    base["wallet_balance"] = 0
                try:
                    cache_key_n = f"notif:unread:{profile_id}"
                    notif_count = get_cache(cache_key_n)
                    if notif_count is None:
                        from services.notification_engine import unread_count
                        notif_count = unread_count(profile_id)
                        set_cache(cache_key_n, notif_count, ttl=60)
                    base["unread_notifications"] = notif_count
                except Exception:
                    base["unread_notifications"] = 0
            return base
        if not session.get("profile_id"):
            return None
        profile = get_current_profile()
        return profile if profile else None
    except Exception as error:
        _log(f"current profile unavailable: {error}")
        return None


def build_homepage_payload(async_warm=False):
    """Consolidated lightweight homepage payload builder with parallelization and tight budget."""
    total_started = time.perf_counter()
    previous_origin = getattr(_TIMING_ROOT, "started_at", None)
    _TIMING_ROOT.started_at = total_started

    def restore_timing_origin():
        if previous_origin is None:
            try:
                delattr(_TIMING_ROOT, "started_at")
            except Exception:
                pass
        else:
            _TIMING_ROOT.started_at = previous_origin

    cache_key_str = cache_key("chain_homepage_v3", "public")
    cache_started = time.perf_counter()
    cached = get_payload() or get_cache(cache_key_str)
    _record_cache_timing("lookup", (time.perf_counter() - cache_started) * 1000)
    if cached is not None:
        total_ms = round((time.perf_counter() - total_started) * 1000, 2)
        _record_homepage_total(total_ms)
        log_info(
            "homepage_timing",
            homepage_start=total_started,
            homepage_total_ms=total_ms,
            homepage_stories_ms=0,
            homepage_reels_ms=0,
            homepage_posts_ms=0,
            homepage_creators_ms=0,
            homepage_live_ms=0,
            stories_ms=0,
            reels_ms=0,
            posts_ms=0,
            profiles_ms=0,
            live_rooms_ms=0,
            hashtags_ms=0,
            suggested_people_ms=0,
            ranking_ms=0,
            cache_lookup_ms=get_homepage_performance_profile().get("cache_lookup_ms", 0),
            cache_store_ms=0,
            profile_queries=0,
            post_queries=0,
            reel_queries=0,
            story_queries=0,
            cache_hit=True,
            cache_hit_ratio=1.0,
            slowest_section=None,
            slowest_section_ms=0,
            recommended_fix="homepage payload served from cache",
        )
        _log_section_timing("build_homepage_payload", total_started)
        restore_timing_origin()
        return cached

    if _fast_local_enabled():
        payload = _empty_homepage_payload("fast_local_defaults")
        set_cache(cache_key_str, payload, ttl=_EMPTY_CACHE_TTL_SECONDS)
        _log_section_timing("build_homepage_payload", total_started)
        restore_timing_origin()
        return payload

    payload = _empty_homepage_payload()

    # Fast exit if Neon circuit is open
    if is_circuit_open():
        payload["issues"].append("neon: unavailable")
        _log_section_timing("build_homepage_payload", total_started)
        restore_timing_origin()
        return payload

    pool_status = get_pool_status()
    if not pool_status.get("recent_success") and not pool_status.get("pool_ready"):
        payload["issues"].append("neon: cold-start-pending")
        _log_section_timing("build_homepage_payload", total_started)
        restore_timing_origin()
        return payload

    started = time.perf_counter()
    section_timings = {}
    section_cache_hits = {}

    def timed_section(cache_name, section_name, loader, ttl=HOMEPAGE_TTL_SECONDS):
        section_started = time.perf_counter()
        value, cache_hit, _ = remember_section(cache_name, loader, ttl=ttl)
        _log_section_timing(section_name, section_started)
        duration_ms = round((time.perf_counter() - section_started) * 1000, 2)
        section_timings[f"{section_name}_ms"] = duration_ms
        section_label = {
            "_fetch_stories": "stories",
            "_fetch_reels": "reels",
            "_fetch_posts": "posts",
            "_fetch_live_rooms": "live_rooms",
            "creator_section": "profiles",
            "dating_previews": "profiles",
        }.get(section_name, section_name)
        _record_section(section_label, duration_ms)
        section_cache_hits[cache_name] = cache_hit
        _record_section_cache_hit(cache_name, cache_hit)
        return value
    
    def fetch_stories():
        cols = _story_select()
        if not cols: return []
        select_cols = ", ".join(f"s.{c}" for c in cols)
        return timed_section(
            "stories",
            "_fetch_stories",
            lambda: _profiled_homepage_query(
                "stories",
                f"SELECT {select_cols}, {', '.join(_PROFILE_JOIN_COLS)} "
                f"FROM chain_stories s "
                f"LEFT JOIN chain_profiles p ON p.id = s.profile_id "
                f"WHERE s.deleted_at IS NULL ORDER BY s.created_at DESC LIMIT {_HOMEPAGE_LIMITS['stories']}",
                timeout_ms=100,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["stories"],
            ),
            ttl=_HOMEPAGE_SECTION_TTLS["stories"],
        )

    def fetch_live():
        cols = _live_select()
        if not cols: return []
        select_cols = ", ".join(f"lr.{c}" for c in cols)
        return timed_section(
            "live_rooms",
            "_fetch_live_rooms",
            lambda: _profiled_homepage_query(
                "live_rooms",
                f"SELECT {select_cols}, {', '.join(_PROFILE_JOIN_COLS)} "
                f"FROM chain_live_rooms lr "
                f"LEFT JOIN chain_profiles p ON p.id = lr.profile_id "
                f"WHERE (lr.is_live = TRUE OR lr.status = 'live') AND lr.deleted_at IS NULL ORDER BY lr.created_at DESC LIMIT {_HOMEPAGE_LIMITS['live_rooms']}",
                timeout_ms=100,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["live_rooms"],
            ),
            ttl=_HOMEPAGE_SECTION_TTLS["live_rooms"],
        )

    def fetch_profiles():
        cols = _profile_select()
        if not cols: return []
        order_by = "followers_count DESC NULLS LAST" if "followers_count" in cols else "created_at DESC NULLS LAST" if "created_at" in cols else "id DESC"
        return timed_section(
            "creator_profiles",
            "creator_section",
            lambda: _profiled_homepage_query(
                "profiles",
                f"SELECT {', '.join(cols)} FROM chain_profiles WHERE is_creator = TRUE AND deleted_at IS NULL ORDER BY {order_by} LIMIT {_HOMEPAGE_LIMITS['recommended_profiles']}",
                timeout_ms=200,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["profiles"],
            ),
            ttl=_HOMEPAGE_SECTION_TTLS["creator_profiles"],
        )

    def fetch_posts():
        cols = _post_select()
        if not cols: return []
        select_cols = ", ".join(f"po.{c}" for c in cols)
        return timed_section(
            "trending_posts",
            "_fetch_posts",
            lambda: _profiled_homepage_query(
                "posts",
                f"SELECT {select_cols}, {', '.join(_PROFILE_JOIN_COLS)} "
                f"FROM chain_posts po "
                f"LEFT JOIN chain_profiles p ON p.id = po.profile_id "
                f"WHERE po.deleted_at IS NULL ORDER BY po.created_at DESC NULLS LAST LIMIT {_HOMEPAGE_LIMITS['trending_posts']}",
                timeout_ms=200,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["posts"],
            ),
            ttl=_HOMEPAGE_SECTION_TTLS["trending_posts"],
        )

    def fetch_matches():
        cols = _profile_select()
        if not cols: return []
        return timed_section(
            "dating_previews",
            "dating_previews",
            lambda: _profiled_homepage_query(
                "profiles",
                f"SELECT {', '.join(cols)} FROM chain_profiles WHERE dating_mode_enabled = TRUE AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 8",
                timeout_ms=200,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["profiles"],
            ),
            ttl=_HOMEPAGE_SECTION_TTLS["reels"],
        )

    def fetch_reels():
        cols = _reel_select()
        if not cols: return []
        select_cols = ", ".join(f"r.{c}" for c in cols)
        return timed_section(
            "reels",
            "_fetch_reels",
            lambda: _profiled_homepage_query(
                "reels",
                f"SELECT {select_cols}, {', '.join(_PROFILE_JOIN_COLS)} "
                f"FROM chain_reels r "
                f"LEFT JOIN chain_profiles p ON p.id = r.profile_id "
                f"WHERE r.deleted_at IS NULL ORDER BY r.created_at DESC LIMIT {_HOMEPAGE_LIMITS['reels']}",
                timeout_ms=100,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["reels"],
            ),
            ttl=60,
        )

    tasks = {
        "stories": fetch_stories,
        "live_rooms": fetch_live,
        "recommended_profiles": fetch_profiles,
        "trending_posts": fetch_posts,
        "dating_matches": fetch_matches,
        "reels": fetch_reels,
    }

    parent_profile = _perf_profile()

    def submit_with_profile(fn):
        def wrapped():
            _PERF_LOCAL.profile = parent_profile
            return fn()
        return _EXECUTOR.submit(wrapped)

    futures = {name: submit_with_profile(fn) for name, fn in tasks.items()}
    log_info(
        "homepage_parallel_sections",
        submitted_sections=sorted(tasks.keys()),
        submitted_count=len(futures),
        max_workers=getattr(_EXECUTOR, "_max_workers", None),
        parallel=True,
    )
    
    # Wait for results with a tight budget
    done_count = 0
    budget_limit = _TOTAL_BUDGET_MS if async_warm else _FAST_FALLBACK_MS
    for name, future in futures.items():
        rem_budget = max(0, (budget_limit / 1000.0) - (time.perf_counter() - started))
        try:
            payload[name] = future.result(timeout=rem_budget)
            done_count += 1
        except Exception:
            future.cancel()
            if "partial_fallback" not in payload["issues"]:
                payload["issues"].append("partial_fallback")

    # 1. Build profile map from inline JOIN data (no additional query)
    profile_map = {}
    for section_name in ("stories", "trending_posts", "live_rooms", "reels"):
        for row in payload.get(section_name, []):
            pid = row.get("profile_id")
            if pid and pid not in profile_map:
                p = _profile_from_row(row)
                if p:
                    profile_map[pid] = p

    # 2. Normalize all collections (inline profile data from JOINs)
    payload["stories"] = [row for row in (_normalize_story(r, profile_map) for r in payload["stories"]) if row.get("id")]
    payload["live_rooms"] = [row for row in (_normalize_live_room(r, profile_map) for r in payload["live_rooms"]) if row.get("id")]
    payload["trending_posts"] = [row for row in (_normalize_post(r, profile_map) for r in payload["trending_posts"]) if row.get("id")]
    payload["recommended_profiles"] = [row for row in (_normalize_profile(r) for r in payload["recommended_profiles"]) if row.get("id")]
    payload["dating_matches"] = [row for row in (_normalize_profile(r) for r in payload["dating_matches"]) if row.get("id")]
    payload["reels"] = [row for row in (_normalize_post(r, profile_map) for r in payload["reels"]) if row.get("id")]

    # ── Phase 73: Real data guard — filter test/demo content ──
    from services.homepage_real_data_guard import filter_feed_posts, filter_profiles
    payload["recommended_profiles"] = filter_profiles(payload["recommended_profiles"])
    payload["dating_matches"] = filter_profiles(payload["dating_matches"])
    payload["trending_posts"] = filter_feed_posts(payload["trending_posts"], profile_map)
    payload["stories"] = filter_feed_posts(payload["stories"], profile_map)
    payload["reels"] = filter_feed_posts(payload["reels"], profile_map)
    _cap_homepage_sections(payload)

    # Final check: if circuit is open or we have no data due to slowness
    if is_circuit_open() and "neon: unavailable" not in payload["issues"]:
        payload["issues"].append("neon: unavailable")

    if not _profile_select():
        if "profiles: schema_mismatch" not in payload["issues"]:
            payload["issues"].append("profiles: schema_mismatch")
    if not _reel_select():
        if "reels: schema_mismatch" not in payload["issues"]:
            payload["issues"].append("reels: schema_mismatch")
    
    payload["stats"] = {
        "stories": len(payload["stories"]),
        "live_rooms": len(payload["live_rooms"]),
        "profiles": len(payload["recommended_profiles"]),
        "posts": len(payload["trending_posts"]),
        "reels": len(payload["reels"]),
    }

    elapsed_ms = (time.perf_counter() - started) * 1000
    total_ms = round((time.perf_counter() - total_started) * 1000, 2)
    _record_homepage_total(total_ms)
    perf_snapshot = get_homepage_performance_profile()
    slowest_section = perf_snapshot.get("slowest_section") or {}
    cache_hit_ratio = _cache_hit_ratio(section_cache_hits)
    log_info(
        "homepage_timing",
        homepage_start=total_started,
        homepage_total_ms=total_ms,
        homepage_stories_ms=section_timings.get("_fetch_stories_ms", 0),
        homepage_reels_ms=section_timings.get("_fetch_reels_ms", 0),
        homepage_posts_ms=section_timings.get("_fetch_posts_ms", 0),
        homepage_creators_ms=section_timings.get("creator_section_ms", 0),
        homepage_live_ms=section_timings.get("_fetch_live_rooms_ms", 0),
        stories_ms=section_timings.get("_fetch_stories_ms", 0),
        reels_ms=section_timings.get("_fetch_reels_ms", 0),
        live_rooms_ms=section_timings.get("_fetch_live_rooms_ms", 0),
        posts_ms=section_timings.get("_fetch_posts_ms", 0),
        profiles_ms=section_timings.get("creator_section_ms", 0),
        hashtags_ms=0,
        suggested_people_ms=0,
        ranking_ms=0,
        cache_lookup_ms=perf_snapshot.get("cache_lookup_ms", 0),
        cache_store_ms=perf_snapshot.get("cache_store_ms", 0),
        profile_queries=perf_snapshot.get("profile_queries", 0),
        post_queries=perf_snapshot.get("post_queries", 0),
        reel_queries=perf_snapshot.get("reel_queries", 0),
        story_queries=perf_snapshot.get("story_queries", 0),
        cache_hit=False,
        section_cache_hits=section_cache_hits,
        cache_hit_ratio=cache_hit_ratio,
        slowest_section=slowest_section.get("section"),
        slowest_section_ms=slowest_section.get("duration_ms", 0),
        slowest_queries=perf_snapshot.get("slowest_queries", []),
        recommended_fix=_recommended_query_fix((perf_snapshot.get("slowest_query") or {}).get("label")),
    )
    if async_warm and total_ms > _WARM_CACHE_BUDGET_MS:
        log_info(
            "homepage_warm_cache_slow",
            homepage_warm_cache_ms=total_ms,
            threshold_ms=_WARM_CACHE_BUDGET_MS,
            slowest_query=perf_snapshot.get("slowest_query"),
            recommended_fix=_recommended_query_fix((perf_snapshot.get("slowest_query") or {}).get("label")),
        )
    if elapsed_ms > _TOTAL_BUDGET_MS:
        payload["issues"].append(f"budget_exceeded: {elapsed_ms:.1f}ms")
        _log_outage_once(f"homepage budget exceeded: {elapsed_ms:.1f}ms")

    # Only cache if we got everything or if this is the async warm
    if (done_count == len(tasks) and not is_circuit_open()) or async_warm:
        cache_store_started = time.perf_counter()
        set_cache(cache_key_str, payload, ttl=_CACHE_TTL_SECONDS)
        set_payload(payload, ttl=_CACHE_TTL_SECONDS)
        _record_cache_timing("store", (time.perf_counter() - cache_store_started) * 1000)
    elif "partial_fallback" in payload["issues"] or "neon: unavailable" in payload["issues"]:
        # Trigger async warm if we fell back
        if not _fast_local_enabled():
            _EXECUTOR.submit(build_homepage_payload, async_warm=True)

    _log_section_timing("build_homepage_payload", total_started)
    if previous_origin is None:
        try:
            delattr(_TIMING_ROOT, "started_at")
        except Exception:
            pass
    else:
        _TIMING_ROOT.started_at = previous_origin
    return payload

def _fetch_groups():
    """Fetch trending/public groups for homepage."""
    cached = get_cache(cache_key("home_groups"))
    if cached is not None:
        return cached
    try:
        from services.group_feature_service import get_public_groups
        groups = get_public_groups(limit=6) or []
        result = [{
            "id": g.get("id"),
            "name": g.get("name") or g.get("display_name") or "Group",
            "display_name": g.get("display_name") or g.get("name") or "Group",
            "member_count": g.get("member_count") or g.get("members_count") or 0,
            "access_type": g.get("access_type") or g.get("type") or "public",
            "cover_url": g.get("cover_url") or g.get("thumbnail_url") or "",
            "description": g.get("description") or g.get("welcome_message") or "",
            "created_label": _format_relative(g.get("created_at")),
        } for g in (groups or [])]
        set_cache(cache_key("home_groups"), result, ttl=30)
        return result
    except Exception as e:
        _log(f"groups unavailable: {e}")
        return []


def _fetch_sponsored_posts():
    """Fetch sponsored/ad posts — only from chain_posts where post_type='sponsored' or sponsored=TRUE."""
    started = time.perf_counter()
    if os.getenv("CHAIN_ENABLE_SPONSORED_HOME", "0").strip().lower() not in {"1", "true", "yes", "on"}:
        _log_section_timing("sponsored_posts_section", started)
        return []
    cached = get_cache(cache_key("home_sponsored"))
    if cached is not None:
        _log_section_timing("sponsored_posts_section", started)
        return cached
    try:
        cols = _post_select()
        if not cols:
            _log_section_timing("sponsored_posts_section", started)
            return []
        available = set(cols)
        where = _build_where(available)
        filters = []
        if "post_type" in available:
            filters.append("post_type = 'sponsored'")
        if "sponsored" in available:
            filters.append("sponsored = TRUE")
        if not filters:
            _log_section_timing("sponsored_posts_section", started)
            return []
        query = "SELECT " + ", ".join(cols) + " FROM chain_posts"
        if where:
            query += " WHERE " + " AND ".join(where) + " AND (" + " OR ".join(filters) + ")"
        else:
            query += " WHERE (" + " OR ".join(filters) + ")"
        query += " ORDER BY created_at DESC NULLS LAST LIMIT 4"
        rows, _ = _run_sql("sponsored_posts", query, [])
        p_map = {}
        result = [{
            **_normalize_post(r, p_map),
            "sponsored": True,
        } for r in rows if r.get("id")]
        set_cache(cache_key("home_sponsored"), result, ttl=60)
        _log_section_timing("sponsored_posts_section", started)
        return result
    except Exception as e:
        _log(f"sponsored_posts unavailable: {e}")
        _log_section_timing("sponsored_posts_section", started)
        return []


def _fetch_announcements():
    """Fetch public announcements for homepage."""
    return []


def _fetch_nearby_users(current_profile=None):
    """Fetch users by matching town/location if available, otherwise recent profiles."""
    started = time.perf_counter()
    if not current_profile:
        _log_section_timing("nearby_users_section", started)
        return []
    cached = get_cache(cache_key("home_nearby"))
    if cached is not None:
        _log_section_timing("nearby_users_section", started)
        return cached
    try:
        cols = _profile_select()
        if not cols:
            _log_section_timing("nearby_users_section", started)
            return []
        available = set(cols)
        where = _build_where(available)
        user_town = (current_profile or {}).get("town") or (current_profile or {}).get("location") or ""
        if user_town and "town" in available:
            query = "SELECT " + ", ".join(cols) + " FROM chain_profiles"
            if where:
                query += " WHERE " + " AND ".join(where) + " AND LOWER(town) = LOWER(%s)"
            else:
                query += " WHERE LOWER(town) = LOWER(%s)"
            query += " ORDER BY created_at DESC NULLS LAST LIMIT 4"
            rows, _ = _run_sql("nearby_users", query, [user_town])
        elif user_town and "location" in available:
            query = "SELECT " + ", ".join(cols) + " FROM chain_profiles"
            if where:
                query += " WHERE " + " AND ".join(where) + " AND LOWER(location) = LOWER(%s)"
            else:
                query += " WHERE LOWER(location) = LOWER(%s)"
            query += " ORDER BY created_at DESC NULLS LAST LIMIT 4"
            rows, _ = _run_sql("nearby_users", query, [user_town])
        else:
            query = "SELECT " + ", ".join(cols) + " FROM chain_profiles"
            if where:
                query += " WHERE " + " AND ".join(where)
            else:
                query += ""
            query += " ORDER BY created_at DESC NULLS LAST LIMIT 4"
            rows, _ = _run_sql("nearby_users", query, [])
        result = [_normalize_profile(r) for r in rows if r.get("id")]
        set_cache(cache_key("home_nearby"), result, ttl=60)
        _log_section_timing("nearby_users_section", started)
        return result
    except Exception as e:
        _log(f"nearby_users unavailable: {e}")
        _log_section_timing("nearby_users_section", started)
        return []


def get_homepage_data(town=None, region=None):
    from flask import session
    page_started = time.perf_counter()
    reset_homepage_performance_profile()
    previous_origin = getattr(_TIMING_ROOT, "started_at", None)
    _TIMING_ROOT.started_at = page_started

    def restore_timing_origin():
        if previous_origin is None:
            try:
                delattr(_TIMING_ROOT, "started_at")
            except Exception:
                pass
        else:
            _TIMING_ROOT.started_at = previous_origin

    has_session_profile = bool(session.get("profile_id") or session.get("auth_user_id") or session.get("user_id"))
    full_cache_key = cache_key("homepage", "full", "public")

    cache_lookup_started = time.perf_counter()
    cached_full = None if has_session_profile else (get_full("public") or get_cache(full_cache_key))
    _record_cache_timing("lookup", (time.perf_counter() - cache_lookup_started) * 1000)
    if cached_full is not None:
        total_ms = round((time.perf_counter() - page_started) * 1000, 2)
        _record_homepage_total(total_ms)
        perf_snapshot = get_homepage_performance_profile()
        log_info(
            "homepage_timing",
            homepage_start=page_started,
            homepage_total_ms=total_ms,
            homepage_stories_ms=0,
            homepage_reels_ms=0,
            homepage_posts_ms=0,
            homepage_creators_ms=0,
            homepage_live_ms=0,
            stories_ms=0,
            reels_ms=0,
            live_rooms_ms=0,
            posts_ms=0,
            profiles_ms=0,
            hashtags_ms=0,
            suggested_people_ms=0,
            ranking_ms=0,
            cache_lookup_ms=perf_snapshot.get("cache_lookup_ms", 0),
            cache_store_ms=0,
            profile_queries=0,
            post_queries=0,
            reel_queries=0,
            story_queries=0,
            cache_hit=True,
            cache_hit_ratio=1.0,
            slowest_section=None,
            slowest_section_ms=0,
            recommended_fix="homepage full payload served from cache",
        )
        restore_timing_origin()
        return cached_full

    current = _safe_current_profile()
    public_data = copy.deepcopy(build_homepage_payload())

    with ThreadPoolExecutor(max_workers=8) as exe:
        f_groups = exe.submit(_fetch_groups)
        f_sponsored = exe.submit(_fetch_sponsored_posts)
        f_announcements = exe.submit(_fetch_announcements)
        f_nearby = exe.submit(_fetch_nearby_users, current)
        f_wallet = exe.submit(_wallet_snapshot, current)

        if current and current.get("id"):
            f_own = exe.submit(fetch_all, """
                SELECT id, profile_id, caption, content, body, media_url, video_url, thumbnail_url, visibility,
                       likes_count, comments_count, created_at, category, deleted_at
                FROM chain_posts
                WHERE deleted_at IS NULL
                  AND (
                    profile_id = %s
                    OR profile_id IN (SELECT id FROM chain_profiles WHERE auth_user_id = %s)
                  )
                ORDER BY created_at DESC NULLS LAST
                LIMIT 4
            """, (current["id"], current.get("auth_user_id")), timeout_ms=500)
        else:
            f_own = None

        f_local = exe.submit(local_content)
        f_stories = exe.submit(active_local_stories)

        def _wait_or_empty(future, section_name, default=None):
            try:
                return future.result(timeout=1.0)
            except Exception:
                log_info("homepage_section_timeout", section=section_name)
                return default if default is not None else []

        groups = _wait_or_empty(f_groups, "groups")
        sponsored_posts = _wait_or_empty(f_sponsored, "sponsored")
        announcements = _wait_or_empty(f_announcements, "announcements")
        nearby_users = _wait_or_empty(f_nearby, "nearby_users")
        wallet = _wait_or_empty(f_wallet, "wallet", default={"coin_balance": 0, "gift_earnings": 0, "label_balance": "0"})
        local = _wait_or_empty(f_local, "local", default={"posts": [], "reels": [], "stories": [], "groups": []})

        if f_own is not None:
            own_rows = _wait_or_empty(f_own, "own_posts")
            if own_rows:
                profile_map = {current.get("id"): _normalize_profile(current)}
                own_posts = [_normalize_post(row, profile_map) for row in own_rows]
                seen = {row.get("id") for row in public_data.get("trending_posts", [])}
                public_data["trending_posts"] = [row for row in own_posts if row.get("id") not in seen] + public_data.get("trending_posts", [])
                public_data["own_recent_posts"] = own_posts
                public_data["latest_own_post_text"] = own_posts[0].get("caption") or own_posts[0].get("excerpt") or ""
            else:
                public_data["own_recent_posts"] = []
                public_data["latest_own_post_text"] = ""
        else:
            public_data["own_recent_posts"] = []
            public_data["latest_own_post_text"] = ""

        active_stories = _wait_or_empty(f_stories, "stories")

    if local["posts"]:
        profile_map = {current.get("id"): _normalize_profile(current)} if current and current.get("id") else {}
        local_posts = [_normalize_post(row, profile_map) for row in local["posts"] if row.get("visibility", "public") == "public" or (current and row.get("profile_id") == current.get("id"))]
        seen = {row.get("id") for row in public_data.get("trending_posts", [])}
        public_data["trending_posts"] = [row for row in local_posts if row.get("id") not in seen] + public_data.get("trending_posts", [])
    if local["reels"]:
        profile_map = {current.get("id"): _normalize_profile(current)} if current and current.get("id") else {}
        local_reels = [_normalize_post(row, profile_map) for row in local["reels"] if row.get("visibility", "public") == "public" or (current and row.get("profile_id") == current.get("id"))]
        seen = {row.get("id") for row in public_data.get("reels", [])}
        public_data["reels"] = [row for row in local_reels if row.get("id") not in seen] + public_data.get("reels", [])
    if local["stories"]:
        profile_map = {current.get("id"): _normalize_profile(current)} if current and current.get("id") else {}
        local_stories = [_normalize_story(row, profile_map) for row in active_stories if row.get("visibility", "public") == "public" or (current and row.get("profile_id") == current.get("id"))]
        seen = {row.get("id") for row in public_data.get("stories", [])}
        public_data["stories"] = [row for row in local_stories if row.get("id") not in seen] + public_data.get("stories", [])
    public_data["stats"]["posts"] = len(public_data.get("trending_posts", []))
    public_data["stats"]["reels"] = len(public_data.get("reels", []))
    public_data["stats"]["stories"] = len(public_data.get("stories", []))
    public_data["groups"] = groups
    public_data["sponsored_posts"] = sponsored_posts
    public_data["announcements"] = announcements
    public_data["nearby_users"] = nearby_users
    public_data["wallet"] = wallet

    # Phase 58 — Premium feed combining
    _own = public_data.get("own_recent_posts", [])
    _trend = public_data.get("trending_posts", [])
    _spon = public_data.get("sponsored_posts", [])
    _ann  = public_data.get("announcements", [])
    _seen_ids = {p.get("id") for p in _own if p.get("id")}
    feed_for_you = list(_own)
    for src in (_spon, _ann, _trend):
        for p in (src if isinstance(src, list) else []):
            if p.get("id") and p["id"] not in _seen_ids:
                feed_for_you.append(p)
                _seen_ids.add(p["id"])
    public_data["feed_for_you"] = feed_for_you[:20]
    public_data["feed_following"] = (_own + [p for p in _trend if p.get("id") not in _seen_ids])[:20]
    public_data["feed_public"] = [p for p in _trend if p.get("visibility", "public") == "public" or not p.get("visibility")][:20]
    public_data["feed_trending"] = sorted(_trend, key=lambda p: -(p.get("likes_count") or 0))[:20]
    _sort_live = sorted(public_data.get("live_rooms", []), key=lambda r: -(r.get("viewer_count") or 0))
    public_data["feed_live"] = _sort_live[:_HOMEPAGE_LIMITS["live_rooms"]]
    public_data["feed_reels"] = public_data.get("reels", [])[:_HOMEPAGE_LIMITS["reels"]]
    public_data["feed_nearby"] = public_data.get("nearby_users", [])[:10]
    public_data["trending_profiles"] = public_data.get("recommended_profiles", [])[:5]
    public_data["following_count"] = (current or {}).get("following_count", 0)

    # Phase 73: Filter any remaining test/demo content
    from services.homepage_real_data_guard import filter_feed_posts, filter_profiles
    if current:
        profile_map = {current.get("id"): current}
    else:
        profile_map = {}
    for src in ("trending_posts", "own_recent_posts", "sponsored_posts"):
        public_data[src] = filter_feed_posts(public_data.get(src, []), profile_map)
    for pkey in ("recommended_profiles", "nearby_users", "trending_profiles"):
        public_data[pkey] = filter_profiles(public_data.get(pkey, []))
    public_data["feed_for_you"] = filter_feed_posts(public_data.get("feed_for_you", []), profile_map)
    public_data["feed_following"] = filter_feed_posts(public_data.get("feed_following", []), profile_map)
    _cap_homepage_sections(public_data)

    # Phase 59: Trending hashtags
    hashtags_started = time.perf_counter()
    public_data["trending_hashtags"] = _trending_hashtags(public_data.get("trending_posts", []))
    hashtags_ms = round((time.perf_counter() - hashtags_started) * 1000, 2)
    _record_section("hashtags", hashtags_ms)

    # Phase 59: Suggested people (prefer verified/avatar/bio/location)
    suggested_started = time.perf_counter()
    public_data["suggested_people"], _, _ = remember_section(
        "suggested_people",
        lambda: _suggested_people(current),
        ttl=120,
    )
    suggested_people_ms = round((time.perf_counter() - suggested_started) * 1000, 2)
    _record_section("suggested_people", suggested_people_ms)

    # Phase 59: Feed ranking
    ranking_started = time.perf_counter()
    feed_for_you_raw = list(public_data.get("feed_for_you", []))
    public_data["feed_for_you_ranked"] = _rank_feed(feed_for_you_raw, current)
    ranking_ms = round((time.perf_counter() - ranking_started) * 1000, 2)
    _record_section("ranking", ranking_ms)

    # Phase 59: Town filter
    public_data["town_filter"] = town or ""
    # Phase 60: Region filter
    public_data["region_filter"] = region or ""

    result = {
        "current": current,
        **public_data,
        "wallet": wallet,
        "hero_story_count": len(public_data["stories"]),
        "hero_live_count": len(public_data["live_rooms"]),
        "hero_profile_count": len(public_data["recommended_profiles"]),
        "hero_post_count": len(public_data["trending_posts"]),
        "missing_sources": public_data["issues"],
        "town_filter": town or "",
        "region_filter": region or "",
    }

    if not current:
        cache_store_started = time.perf_counter()
        set_cache(full_cache_key, result, ttl=_CACHE_TTL_SECONDS)
        set_full("public", result, ttl=_CACHE_TTL_SECONDS)
        _record_cache_timing("store", (time.perf_counter() - cache_store_started) * 1000)
    total_ms = round((time.perf_counter() - page_started) * 1000, 2)
    _record_homepage_total(total_ms)
    perf_snapshot = get_homepage_performance_profile()
    sections = perf_snapshot.get("sections") or {}
    slowest_section = perf_snapshot.get("slowest_section") or {}
    cache_hit_ratio = _cache_hit_ratio(perf_snapshot.get("section_cache_hits") or {})
    log_info(
        "homepage_timing",
        homepage_start=page_started,
        homepage_total_ms=total_ms,
        homepage_stories_ms=sections.get("stories", 0),
        homepage_reels_ms=sections.get("reels", 0),
        homepage_posts_ms=sections.get("posts", 0),
        homepage_creators_ms=sections.get("profiles", 0),
        homepage_live_ms=sections.get("live_rooms", 0),
        stories_ms=sections.get("stories", 0),
        reels_ms=sections.get("reels", 0),
        posts_ms=sections.get("posts", 0),
        profiles_ms=sections.get("profiles", 0),
        live_rooms_ms=sections.get("live_rooms", 0),
        hashtags_ms=hashtags_ms,
        suggested_people_ms=suggested_people_ms,
        ranking_ms=ranking_ms,
        cache_lookup_ms=perf_snapshot.get("cache_lookup_ms", 0),
        cache_store_ms=perf_snapshot.get("cache_store_ms", 0),
        profile_queries=perf_snapshot.get("profile_queries", 0),
        post_queries=perf_snapshot.get("post_queries", 0),
        reel_queries=perf_snapshot.get("reel_queries", 0),
        story_queries=perf_snapshot.get("story_queries", 0),
        cache_hit=False,
        cache_hit_ratio=cache_hit_ratio,
        slowest_section=slowest_section.get("section"),
        slowest_section_ms=slowest_section.get("duration_ms", 0),
        slowest_queries=perf_snapshot.get("slowest_queries", []),
        recommended_fix=_recommended_query_fix((perf_snapshot.get("slowest_query") or {}).get("label")),
    )
    _log_section_timing("get_homepage_data", page_started)
    restore_timing_origin()
    return result


# ================================================================
# Phase 59 — get_feed_tab() — Tab-filtered feed with pagination
# ================================================================

def get_feed_tab(profile_id=None, tab="for_you", page=1, limit=20):
    """
    Return (items_list, has_more) for a given feed tab.
    - for_you:     public + followed posts + sponsored + announcements
    - following:   posts from profiles current user follows
    - public:      public posts only
    - nearby:      public posts with location / nearby users
    - live:        live rooms
    - reels:       reels content
    - trending:    posts sorted by engagement
    """
    from services.homepage_real_data_guard import filter_feed_posts

    offset = max(0, (page - 1) * limit)
    cache_key_str = cache_key("home_feed_tab", tab, page, limit, profile_id or "anon")
    if page == 1 and tab in {"for_you", "public", "trending", "reels", "live"}:
        cached = get_cache(cache_key_str)
        if cached is not None:
            return cached
    tabs = {
        "for_you": _feed_for_you,
        "following": _feed_following,
        "public": _feed_public_posts,
        "nearby": _feed_nearby,
        "live": _feed_live,
        "reels": _feed_reels,
        "trending": _feed_trending,
    }
    fetcher = tabs.get(tab, _feed_for_you)
    try:
        items = fetcher(profile_id=profile_id, limit=limit, offset=offset)
        items = filter_feed_posts(items[:limit])
        has_more = len(items) >= limit
        result = (items[:limit], has_more)
        if page == 1 and tab in {"for_you", "public", "trending", "reels", "live"}:
            set_cache(cache_key_str, result, ttl=20)
        return result
    except Exception:
        return [], False


def _normalize_items(rows, default_type="post"):
    """Normalize raw rows to feed item dicts with type tag."""
    result = []
    for r in (rows or []):
        if not isinstance(r, dict) or not r.get("id"):
            continue
        item_type = r.get("_type") or r.get("type") or default_type
        normalized = {
            "id": str(r.get("id")),
            "type": item_type,
            "profile_id": str(r.get("profile_id") or r.get("creator_id") or ""),
            "display_name": r.get("display_name") or r.get("creator_name") or "",
            "username": r.get("username") or "",
            "avatar_url": r.get("avatar_url") or r.get("creator_avatar") or "",
            "verified": bool(r.get("is_verified") or r.get("verified") or False),
            "text": r.get("caption") or r.get("excerpt") or r.get("body") or r.get("title") or "",
            "media_url": r.get("media_url") or r.get("thumbnail_url") or r.get("cover_url") or "",
            "video_url": r.get("video_url") or "",
            "likes_count": r.get("likes_count") or 0,
            "comments_count": r.get("comments_count") or 0,
            "view_count": r.get("view_count") or r.get("viewer_count") or 0,
            "created_label": r.get("created_label") or _format_relative(r.get("created_at")),
            "location": r.get("town_tag") or r.get("location") or "",
            "visibility": r.get("visibility") or "public",
            "sponsored": bool(r.get("sponsored") or False),
        }
        if item_type == "live" and r.get("watch_url"):
            normalized["watch_url"] = r.get("watch_url")
        if item_type == "live" and r.get("category"):
            normalized["category"] = r.get("category")
        result.append(normalized)
    return result


def _profile_map_for_ids(profile_ids):
    """Load profiles for a list of profile IDs and return {id: profile_dict}."""
    if not profile_ids:
        return {}
    unique = list(set(str(pid) for pid in profile_ids if pid))
    if not unique:
        return {}
    try:
        placeholders = ",".join("%s" for _ in unique)
        rows = fast_query(
            f"SELECT id, username, display_name, full_name, avatar_url, is_verified, verified "
            f"FROM chain_profiles WHERE id IN ({placeholders}) LIMIT %s",
            list(unique) + [len(unique)], timeout_ms=500, default=[]
        )
        return {str(r.get("id")): r for r in rows if isinstance(r, dict) and r.get("id")}
    except Exception:
        return {}


def _post_select_alias(alias="po"):
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    return cols, ", ".join(f"{alias}.{col}" for col in cols)


def _post_rows_with_profile(where_sql, order_sql, limit, offset=0, params=None, timeout_ms=500):
    cols, select_sql = _post_select_alias("po")
    rows = fast_query(
        f"""
        SELECT {select_sql},
               p.username,
               p.display_name,
               p.full_name,
               p.avatar_url,
               p.is_verified,
               p.verified
        FROM chain_posts po
        LEFT JOIN chain_profiles p ON p.id = po.profile_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT %s OFFSET %s
        """,
        tuple(params or []) + (limit, offset),
        timeout_ms=timeout_ms,
        default=[],
    )
    return rows or []


def _feed_for_you(profile_id=None, limit=20, offset=0):
    items = []
    seen = set()
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    if not cols:
        return items
    try:
        rows = _post_rows_with_profile(
            "po.deleted_at IS NULL AND (po.visibility IS NULL OR po.visibility = 'public')",
            "po.created_at DESC NULLS LAST",
            limit,
            offset=offset,
            timeout_ms=500,
        )
        for r in rows:
            if not isinstance(r, dict):
                continue
            if r.get("id") and r["id"] not in seen:
                items.append(r)
                seen.add(r["id"])
    except Exception:
        pass
    try:
        spon = _fetch_sponsored_posts()
        for r in spon:
            if r.get("id") and r["id"] not in seen:
                r["sponsored"] = True
                items.append(r)
                seen.add(r["id"])
    except Exception:
        pass
    result = []
    for r in items:
        result.append(r)
    return _normalize_items(result)


def _feed_following(profile_id=None, limit=20, offset=0):
    if not profile_id:
        return []
    try:
        following = fast_query(
            "SELECT following_id FROM chain_follows WHERE follower_id = %s LIMIT 200",
            (profile_id,), timeout_ms=300, default=[]
        )
        fids = [str(r["following_id"]) for r in following if r.get("following_id")]
    except Exception:
        fids = []
    if not fids:
        return []
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    try:
        placeholders = ",".join(f"'{fid}'" for fid in fids[:50])
        query = f"SELECT {', '.join(cols)} FROM chain_posts WHERE deleted_at IS NULL AND profile_id IN ({placeholders}) ORDER BY created_at DESC LIMIT {limit + offset}"
        rows = fast_query(query, timeout_ms=500, default=[])
    except Exception:
        rows = []
    pids = [r.get("profile_id") for r in rows]
    pmap = _profile_map_for_ids(pids)
    result = []
    for r in rows[offset:]:
        pid = r.get("profile_id")
        p = pmap.get(str(pid)) if pid else None
        if p:
            r["display_name"] = p.get("display_name") or p.get("full_name") or ""
            r["username"] = p.get("username") or ""
            r["avatar_url"] = p.get("avatar_url") or ""
            r["is_verified"] = p.get("is_verified") or p.get("verified") or False
        result.append(r)
    return _normalize_items(result)


def _feed_public_posts(profile_id=None, limit=20, offset=0):
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    if not cols:
        return []
    try:
        rows = _post_rows_with_profile(
            "po.deleted_at IS NULL AND (po.visibility IS NULL OR po.visibility = 'public')",
            "po.created_at DESC NULLS LAST",
            limit,
            offset=offset,
            timeout_ms=500,
        )
    except Exception:
        rows = []
    return _normalize_items(rows)


def _feed_trending(profile_id=None, limit=20, offset=0):
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    if not cols:
        return []
    try:
        rows = _post_rows_with_profile(
            "po.deleted_at IS NULL",
            "(COALESCE(po.likes_count,0) + COALESCE(po.comments_count,0)) DESC, po.created_at DESC NULLS LAST",
            limit,
            offset=offset,
            timeout_ms=500,
        )
    except Exception:
        rows = []
    return _normalize_items(rows)


def _feed_nearby(profile_id=None, limit=20, offset=0):
    try:
        cols = _profile_select()
        for extra in ("location", "bio", "created_at"):
            if extra in _table_columns("chain_profiles") and extra not in cols:
                cols.append(extra)
        if not cols:
            return []
        rows = fast_query(
            "SELECT " + ", ".join(cols) + " "
            "FROM chain_profiles WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT "
            + str(limit + offset),
            timeout_ms=500, default=[]
        )
    except Exception:
        rows = []
    result = []
    for r in rows[offset:]:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        result.append({
            "id": str(r.get("id")),
            "type": "suggested_user",
            "profile_id": str(r["id"]),
            "display_name": r.get("display_name") or r.get("full_name") or "User",
            "username": r.get("username") or "",
            "avatar_url": r.get("avatar_url") or "",
            "verified": bool(r.get("is_verified") or r.get("verified") or False),
            "text": r.get("bio") or r.get("location") or "",
            "location": r.get("location") or "",
            "likes_count": 0,
            "comments_count": 0,
            "view_count": 0,
            "created_label": "",
            "visibility": "public",
            "sponsored": False,
        })
    return result


def _feed_live(profile_id=None, limit=20, offset=0):
    try:
        cols = _live_select()
        if not cols:
            return []
        available = set(cols)
        live_clause = "is_live = TRUE" if "is_live" in available else "status = 'live'" if "status" in available else "TRUE"
        order_col = "viewer_count" if "viewer_count" in available else "created_at"
        rows = fast_query(
            f"SELECT {', '.join(cols)} FROM chain_live_rooms WHERE deleted_at IS NULL AND {live_clause} ORDER BY {order_col} DESC NULLS LAST LIMIT {limit + offset}",
            timeout_ms=500, default=[]
        )
    except Exception:
        rows = []
    pids = []
    for r in rows:
        pids.append(r.get("profile_id") or r.get("host_id") or r.get("creator_id"))
    pmap = _profile_map_for_ids(pids)
    result = []
    for r in rows[offset:]:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        pid = r.get("profile_id") or r.get("host_id") or r.get("creator_id")
        p = pmap.get(str(pid)) if pid else None
        title = r.get("title") or ""
        result.append({
            "id": str(r.get("id")),
            "type": "live",
            "profile_id": str(pid) if pid else "",
            "display_name": (p.get("display_name") or p.get("full_name") or "Live") if p else "Live",
            "username": p.get("username") if p else "",
            "avatar_url": p.get("avatar_url") if p else "",
            "verified": bool(p.get("is_verified") or p.get("verified")) if p else False,
            "text": title,
            "media_url": r.get("cover_url") or "",
            "view_count": r.get("viewer_count") or 0,
            "created_label": "",
            "location": r.get("category") or "",
            "visibility": "public",
            "sponsored": False,
            "watch_url": f"/live/{r.get('id')}",
            "category": r.get("category") or "",
        })
    return result


def _feed_reels(profile_id=None, limit=20, offset=0):
    try:
        cols = _reel_select()
        for extra in ("likes_count", "comments_count", "view_count", "media_url"):
            if extra in _table_columns("chain_reels") and extra not in cols:
                cols.append(extra)
        if not cols:
            return []
        query = f"SELECT {', '.join(cols)} FROM chain_reels WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT {limit + offset}"
        rows = fast_query(query, timeout_ms=500, default=[])
    except Exception:
        rows = []
    pids = [r.get("profile_id") for r in rows]
    pmap = _profile_map_for_ids(pids)
    result = []
    for r in rows[offset:]:
        if not isinstance(r, dict) or not r.get("id"):
            continue
        pid = r.get("profile_id")
        p = pmap.get(str(pid)) if pid else None
        result.append({
            "id": str(r.get("id")),
            "type": "reel",
            "profile_id": str(pid) if pid else "",
            "display_name": (p.get("display_name") or p.get("full_name") or "Creator") if p else "Creator",
            "username": p.get("username") if p else "",
            "avatar_url": p.get("avatar_url") if p else "",
            "verified": bool(p.get("is_verified") or p.get("verified")) if p else False,
            "text": r.get("caption") or "",
            "media_url": r.get("thumbnail_url") or r.get("media_url") or "",
            "video_url": r.get("video_url") or "",
            "likes_count": r.get("likes_count") or 0,
            "comments_count": r.get("comments_count") or 0,
            "view_count": r.get("view_count") or 0,
            "created_label": _format_relative(r.get("created_at")),
            "visibility": "public",
            "sponsored": False,
        })
    return result


# ================================================================
# Phase 59 — Trending Hashtags Engine
# ================================================================

def _trending_hashtags(posts, limit=10):
    import re
    from collections import Counter
    from services.homepage_real_data_guard import _SHOW_ALL, _TEST_CONTENT_PATTERNS, _TEST_USER_PATTERNS

    counter = Counter()
    for p in (posts or []):
        content = p.get("caption") or p.get("excerpt") or p.get("text") or p.get("body") or ""
        tags = re.findall(r"#(\w+)", content)
        for t in tags:
            key = t.lower()
            if not _SHOW_ALL:
                if any(pat.search(key) for pat in _TEST_CONTENT_PATTERNS):
                    continue
            counter[key] += 1
    top = counter.most_common(limit)
    return [
        {"tag": tag, "count": count, "url": f"/search?q=%23{tag}"}
        for tag, count in top
    ]


# ================================================================
# Phase 59 — Suggested People Engine
# ================================================================

def _suggested_people(current_user=None, limit=5):
    if is_circuit_open():
        return []
    try:
        cache_key_str = cache_key("suggested_people", str(current_user.get("id")) if current_user else "anonymous")
        cached = get_cache(cache_key_str)
        if cached is not None:
            return cached

        cols = _profile_select()
        if not cols:
            return []
        available = set(cols)

        score_parts = []
        for col, weight in [("avatar_url", "2"), ("bio", "1.5"), ("location", "1"), ("town", "1")]:
            if col in available:
                score_parts.append(f"(CASE WHEN {col} IS NOT NULL AND {col} <> '' THEN {weight} ELSE 0 END)")
        if "is_verified" in available:
            score_parts.append("(CASE WHEN is_verified IS TRUE THEN 2 ELSE 0 END)")
        if "verified" in available:
            score_parts.append("(CASE WHEN verified IS TRUE THEN 1 ELSE 0 END)")
        if not score_parts:
            score_parts.append("0")
        score_expr = " + ".join(score_parts)

        where = _build_where(available)
        exclude = ""
        if current_user and current_user.get("id"):
            exclude = f" AND id != %s"
        query = f"SELECT {', '.join(cols)}, ({score_expr}) AS _score FROM chain_profiles"
        query += f" WHERE {' AND '.join(where)}{exclude} ORDER BY _score DESC, created_at DESC NULLS LAST LIMIT %s"
        params = []
        if current_user and current_user.get("id"):
            params.append(current_user["id"])
        params.append(limit + 5)
        rows, _ = _run_sql("suggested_people", query, params, timeout_ms=1000)
        result = []
        seen_ids = set()
        for r in (rows or []):
            if not isinstance(r, dict) or not r.get("id"):
                continue
            pid = r.get("id")
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            profile = _normalize_profile(r)
            if profile and profile.get("id") and len(result) < limit:
                result.append(profile)

        from services.homepage_real_data_guard import filter_profiles
        result = filter_profiles(result)

        if not result:
            recent, _ = _fetch_profiles(limit=limit)
            result = [_normalize_profile(r) for r in recent if r.get("id")]
            result = filter_profiles(result)

        result = result[:limit]
        set_cache(cache_key_str, result, ttl=300)
        return result
    except Exception:
        return []


# ================================================================
# Phase 59 — Feed Ranking Helper
# ================================================================

def _rank_feed(items, current_user=None):
    if not items:
        return items

    now = datetime.now(timezone.utc)
    user_town = None
    if current_user:
        user_town = (current_user.get("town") or current_user.get("location") or "").strip().lower()

    scored = []
    for item in items:
        score = 0.0

        raw = item.get("created_at") or item.get("created_label") or ""
        if raw:
            try:
                if isinstance(raw, datetime):
                    age_hours = (now - raw).total_seconds() / 3600
                else:
                    parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
                    age_hours = (now - parsed).total_seconds() / 3600
                if age_hours < 6:
                    score += 30
                elif age_hours < 24:
                    score += 20
                elif age_hours < 48:
                    score += 10
            except (ValueError, TypeError):
                score += 5

        likes = float(item.get("likes_count") or 0)
        score += min(likes * 2, 40)

        comments = float(item.get("comments_count") or 0)
        score += min(comments * 3, 30)

        views = float(item.get("view_count") or 0)
        score += min(views * 0.5, 20)

        if item.get("verified") or item.get("is_verified"):
            score += 15

        item_town = (item.get("location") or item.get("town_tag") or "").strip().lower()
        if user_town and item_town and user_town == item_town:
            score += 25
        elif user_town and item_town:
            if user_town in item_town or item_town in user_town:
                score += 10

        scored.append((score, item))

    scored.sort(key=lambda x: -x[0])
    return [item for _, item in scored]


# ================================================================
# Phase 69 — Public Helper Functions
# ================================================================

def build_current_user_card():
    """Return a rich current-user card dict, or None if not logged in."""
    current = _safe_current_profile()
    if not current:
        return None
    base = dict(current)
    base["initial"] = (current.get("display_name") or current.get("username") or "?")[:1].upper()
    base["profile_url"] = f"/profile/@{current.get('username')}" if current.get("username") else "/discover/"
    return base


def fetch_homepage_stories(limit=12):
    """Return normalized story items for the homepage story strip."""
    try:
        payload = build_homepage_payload()
        stories = payload.get("stories", [])
        return stories[:limit]
    except Exception:
        return []


def fetch_homepage_reels(limit=8):
    """Return normalized reel items for the homepage reels section."""
    try:
        payload = build_homepage_payload()
        reels = payload.get("reels", [])
        return [_normalize_reel_for_preview(r) for r in reels[:limit]]
    except Exception:
        return []


def fetch_homepage_posts(limit=20, offset=0):
    """Return normalized public feed posts."""
    try:
        return _feed_public_posts(limit=limit, offset=offset)
    except Exception:
        return []


def fetch_trending_creators(limit=10):
    """Return top creators ordered by followers or recency."""
    try:
        cache_key_str = cache_key("trending_creators", str(limit))
        cached = get_cache(cache_key_str)
        if cached is not None:
            return cached

        cols = _profile_select()
        if not cols:
            return []
        order = "followers_count DESC NULLS LAST" if "followers_count" in cols else "created_at DESC NULLS LAST"
        rows, _ = _run_sql(
            "trending_creators",
            f"SELECT {', '.join(cols)} FROM chain_profiles WHERE is_creator = TRUE AND deleted_at IS NULL ORDER BY {order} LIMIT %s",
            [limit],
            timeout_ms=1000,
        )
        from services.homepage_real_data_guard import filter_profiles
        result = filter_profiles([_normalize_profile(r) for r in rows if r.get("id")])
        set_cache(cache_key_str, result, ttl=300)
        return result
    except Exception:
        return []


def fetch_suggested_people(current_user=None, limit=5):
    """Return suggested people excluding current user and test profiles."""
    try:
        return _suggested_people(current_user=current_user, limit=limit)
    except Exception:
        return []


def fetch_trending_hashtags(posts=None, limit=10):
    """Return trending hashtags extracted from posts."""
    try:
        if posts is None:
            payload = build_homepage_payload()
            posts = payload.get("trending_posts", [])
        return _trending_hashtags(posts, limit=limit)
    except Exception:
        return []


def fetch_popular_towns(limit=10):
    """Return popular Namibian towns based on profile density."""
    try:
        rows, _ = _run_sql(
            "popular_towns",
            """
            SELECT LOWER(TRIM(town)) AS town_name, COUNT(*) AS profile_count
            FROM chain_profiles
            WHERE town IS NOT NULL AND TRIM(town) <> ''
              AND deleted_at IS NULL
            GROUP BY LOWER(TRIM(town))
            ORDER BY profile_count DESC
            LIMIT %s
            """,
            [limit],
        )
        return [
            {"name": r["town_name"].title(), "count": r["profile_count"], "url": f"/?town={r['town_name']}"}
            for r in rows if r.get("town_name")
        ]
    except Exception:
        return []


def _normalize_reel_for_preview(reel):
    """Ensure reel dict has all fields the template expects."""
    if not reel:
        return {}
    for key in ("likes_count", "comments_count", "view_count", "video_url", "media_url", "avatar_url", "text", "display_name"):
        reel.setdefault(key, 0 if "count" in key else "")
    return reel


def get_profile_avatar_url(profile):
    """Return best available avatar URL from a profile dict.

    Priority:
    1. avatar_url
    2. photo_url
    3. thumbnail_url
    4. local static upload path (profile_id based)
    5. None  — caller should show initials fallback

    Returns None if no usable URL is found (caller must render initials).
    """
    if not profile or not isinstance(profile, dict):
        return None
    url = (
        profile.get("avatar_url")
        or profile.get("photo_url")
        or profile.get("thumbnail_url")
        or profile.get("avatar_storage_path")
        or profile.get("avatar_path")
        or profile.get("profile_picture")
        or profile.get("image_url")
    )
    if url:
        return url
    pid = profile.get("id")
    if pid:
        local_path = f"/static/uploads/profile/avatars/{pid}.jpg"
        if os.path.isfile(os.path.join(os.path.dirname(__file__), "..", local_path.lstrip("/"))):
            return local_path
        local_path = f"/static/uploads/profile/avatars/{pid}.png"
        if os.path.isfile(os.path.join(os.path.dirname(__file__), "..", local_path.lstrip("/"))):
            return local_path
    return None


# ================================================================
# Phase 71 — TikTok-style Reel Feed Payload
# ================================================================

def _time_budget(deadline):
    return time.perf_counter() < deadline


def build_tiktok_home_payload(exclude_test_content=True):
    """Return lightweight TikTok-style homepage payload with reels feed."""
    start = time.perf_counter()
    budget_800 = start + 0.8
    budget_1000 = start + 1.0
    payload = {
        "current": _safe_current_profile(),
        "reels_feed": [],
        "suggested_creators": [],
        "trending_hashtags": [],
        "popular_towns": [],
        "following_map": {},
        "stats": {"reels": 0, "suggested": 0},
    }
    try:
        current = payload["current"]
        profile_id = current.get("id") if current else None
        reels = []

        if _time_budget(budget_1000):
            from services.reels_service import get_reel_feed
            reels = get_reel_feed(limit=30) if _time_budget(budget_1000) else reels
            if exclude_test_content and reels:
                reels = filter_content(reels)
            if _time_budget(budget_1000):
                try:
                    from services.video_interest_service import rank_reels_for_viewer
                    reels = rank_reels_for_viewer(profile_id, reels=reels, limit=30)
                except Exception:
                    pass

            follow_map = {}
            if profile_id and reels:
                creator_ids = {r.get("profile_id") for r in reels if r.get("profile_id") and r.get("profile_id") != profile_id}
                if creator_ids:
                    from services.reels_service import batch_is_following
                    following = batch_is_following(profile_id, creator_ids)
                    follow_map = {pid: pid in following for pid in creator_ids}

            items = []
            for r in reels:
                pid = r.get("profile_id")
                items.append({
                    "id": r.get("id"),
                    "video_url": r.get("video_url") or "",
                    "thumbnail_url": r.get("thumbnail_url") or r.get("media_url") or "",
                    "caption": (r.get("caption") or "")[:200],
                    "music_title": r.get("music_title") or "",
                    "hashtags": _extract_hashtags(r.get("caption") or ""),
                    "duration_seconds": r.get("duration_seconds") or 0,
                    "profile_id": pid,
                    "username": r.get("username") or "",
                    "display_name": r.get("display_name") or r.get("username") or "Creator",
                    "avatar_url": get_profile_avatar_url(r) or "",
                    "is_verified": bool(r.get("is_verified") or r.get("verified")),
                    "likes_count": r.get("likes_count") or 0,
                    "comments_count": r.get("comments_count") or 0,
                    "views_count": r.get("views_count") or 0,
                    "shares_count": r.get("shares_count") or 0,
                    "is_followed": follow_map.get(pid, False),
                    "is_liked": False,
                    "is_saved": False,
                })

            payload["reels_feed"] = items
            payload["following_map"] = follow_map
            payload["stats"]["reels"] = len(items)

        # Suggested creators
        if _time_budget(budget_800):
            try:
                from services.smart_suggestion_service import get_smart_suggestions, build_recommendation_cards
                suggested = get_smart_suggestions(profile_id, limit=5)
                payload["recommendation_cards"] = build_recommendation_cards(profile_id, limit=3)
            except Exception:
                suggested = _suggested_people(current_user=current, limit=5)
                if exclude_test_content:
                    suggested = filter_profiles(suggested)
                payload["recommendation_cards"] = []
            payload["suggested_creators"] = suggested
            payload["smart_suggestions"] = suggested
            payload["stats"]["suggested"] = len(suggested)

        # Trending hashtags from reels captions
        if _time_budget(budget_1000) and reels:
            payload["trending_hashtags"] = _trending_hashtags(reels, limit=8)

        # Popular towns — cached 10 minutes
        if _time_budget(budget_800):
            from engines.cache_engine import get_cache, set_cache, cache_key
            towns = get_cache(cache_key("homepage", "popular_towns"))
            if towns is None:
                towns = fetch_popular_towns(limit=6)
                set_cache(cache_key("homepage", "popular_towns"), towns, ttl=600)
            payload["popular_towns"] = towns

    except Exception as e:
        _log(f"build_tiktok_home_payload error: {e}")

    elapsed = (time.perf_counter() - start) * 1000
    if elapsed > 3000:
        _log(f"build_tiktok_home_payload slow: {elapsed:.0f}ms")
    return payload


def _extract_hashtags(text):
    """Extract hashtag strings from text."""
    if not text:
        return []
    import re
    return re.findall(r"#(\w+)", text)
