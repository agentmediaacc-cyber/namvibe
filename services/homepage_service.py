import copy
import time
import threading
import os
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


_CACHE_TTL_SECONDS = HOMEPAGE_TTL_SECONDS
_EMPTY_CACHE_TTL_SECONDS = 300
_QUERY_TIMEOUT_MS = 1500
_TOTAL_BUDGET_MS = 1200
_FAST_FALLBACK_MS = 2000
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
        lambda: profiled_query(
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
            "is_verified",
            "verified",
            "is_creator",
            "creator_category",
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
    rows, issue = _run_sql("posts", query, [8])
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
        story_rows, issue = _run_sql("stories", query, [12])
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
        params.append(12)
        status_rows, issue = _run_sql("status_posts", query, params)
        if issue:
            issues.append(issue)

    combined = [row for row in story_rows if row.get("id")]
    for row in status_rows:
        if row.get("id"):
            combined.append(row)
    combined.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    return combined[:12], issues


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
    rows, issue = _run_sql("reels", query, [8])
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
    rows, issue = _run_sql("live_rooms", query, [8])
    live_only = [row for row in rows if _boolish(row.get("is_live")) or _clean_text(row.get("status")).lower() == "live"]
    return live_only[:8], [issue] if issue else []


def _load_profile_map(profile_ids):
    started = time.perf_counter()
    columns = _profile_select()
    if not profile_ids or not columns:
        _log_section_timing("_load_profile_map", started)
        return {}
    result = batch_load_profiles(profile_ids, columns, _build_where, _normalize_profile, timeout_ms=200)
    _log_section_timing("_load_profile_map", started)
    return result


def _normalize_profile(row):
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
    profile = profile_map.get(row.get("profile_id")) or {}
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
    }


def _normalize_live_room(row, profile_map):
    profile_id = _first_present(row, ["profile_id", "host_id", "creator_id"])
    profile = profile_map.get(profile_id) or {}
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
    profile = profile_map.get(row.get("profile_id")) or {}
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
            return {
                "id": session.get("profile_id"),
                "auth_user_id": auth_user_id,
                "email": email,
                "username": username,
                "full_name": full_name,
                "display_name": full_name,
                "avatar_url": session.get("avatar_url"),
                "profile_completed": bool(session.get("profile_completed")),
            }
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
    cached = get_payload() or get_cache(cache_key_str)
    if cached is not None:
        log_info(
            "homepage_timing",
            homepage_total_ms=round((time.perf_counter() - total_started) * 1000, 2),
            cache_hit=True,
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
        section_timings[f"{section_name}_ms"] = round((time.perf_counter() - section_started) * 1000, 2)
        section_cache_hits[cache_name] = cache_hit
        return value
    
    def fetch_stories():
        cols = _story_select()
        if not cols: return []
        return timed_section(
            "stories",
            "_fetch_stories",
            lambda: profiled_query(
                "stories",
                f"SELECT {', '.join(cols)} FROM chain_stories WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 12",
                timeout_ms=100,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["stories"],
            ),
        )

    def fetch_live():
        cols = _live_select()
        if not cols: return []
        return timed_section(
            "live_rooms",
            "_fetch_live_rooms",
            lambda: profiled_query(
                "live_rooms",
                f"SELECT {', '.join(cols)} FROM chain_live_rooms WHERE (is_live = TRUE OR status = 'live') AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 8",
                timeout_ms=100,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["live_rooms"],
            ),
        )

    def fetch_profiles():
        cols = _profile_select()
        if not cols: return []
        return timed_section(
            "creator_profiles",
            "creator_section",
            lambda: profiled_query(
                "profiles",
                f"SELECT {', '.join(cols)} FROM chain_profiles WHERE is_creator = TRUE AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 10",
                timeout_ms=200,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["profiles"],
            ),
            ttl=60,
        )

    def fetch_posts():
        cols = _post_select()
        if not cols: return []
        return timed_section(
            "trending_posts",
            "_fetch_posts",
            lambda: profiled_query(
                "posts",
                f"SELECT {', '.join(cols)} FROM chain_posts WHERE deleted_at IS NULL ORDER BY created_at DESC NULLS LAST LIMIT 8",
                timeout_ms=200,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["posts"],
            ),
        )

    def fetch_matches():
        cols = _profile_select()
        if not cols: return []
        return timed_section(
            "dating_previews",
            "dating_previews",
            lambda: profiled_query(
                "profiles",
                f"SELECT {', '.join(cols)} FROM chain_profiles WHERE dating_mode_enabled = TRUE AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 8",
                timeout_ms=200,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["profiles"],
            ),
            ttl=60,
        )

    def fetch_reels():
        cols = _reel_select()
        if not cols: return []
        return timed_section(
            "reels",
            "_fetch_reels",
            lambda: profiled_query(
                "reels",
                f"SELECT {', '.join(cols)} FROM chain_reels WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 8",
                timeout_ms=100,
                default=[],
                budget_ms=HOMEPAGE_QUERY_BUDGET_MS["reels"],
            ),
        )

    tasks = {
        "stories": fetch_stories,
        "live_rooms": fetch_live,
        "recommended_profiles": fetch_profiles,
        "trending_posts": fetch_posts,
        "dating_matches": fetch_matches,
        "reels": fetch_reels,
    }

    futures = {name: _EXECUTOR.submit(fn) for name, fn in tasks.items()}
    
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

    # 1. Collect all profile IDs for normalization
    profile_ids = []
    for row in payload["stories"]: profile_ids.append(row.get("profile_id"))
    for row in payload["trending_posts"]: profile_ids.append(row.get("profile_id"))
    for row in payload["live_rooms"]: 
        profile_ids.append(_first_present(row, ["profile_id", "host_id", "creator_id"]))
    for row in payload["recommended_profiles"]: profile_ids.append(row.get("id"))
    for row in payload["dating_matches"]: profile_ids.append(row.get("id"))
    for row in payload["reels"]: profile_ids.append(row.get("profile_id"))

    # 2. Load the profile map
    profile_started = time.perf_counter()
    profile_map = _load_profile_map(profile_ids)
    section_timings["profiles_ms"] = round((time.perf_counter() - profile_started) * 1000, 2)

    # 3. Normalize all collections
    payload["stories"] = [row for row in (_normalize_story(r, profile_map) for r in payload["stories"]) if row.get("id")]
    payload["live_rooms"] = [row for row in (_normalize_live_room(r, profile_map) for r in payload["live_rooms"]) if row.get("id")]
    payload["trending_posts"] = [row for row in (_normalize_post(r, profile_map) for r in payload["trending_posts"]) if row.get("id")]
    payload["recommended_profiles"] = [row for row in (_normalize_profile(r) for r in payload["recommended_profiles"]) if row.get("id")]
    payload["dating_matches"] = [row for row in (_normalize_profile(r) for r in payload["dating_matches"]) if row.get("id")]
    payload["reels"] = [row for row in (_normalize_post(r, profile_map) for r in payload["reels"]) if row.get("id")]

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
    log_info(
        "homepage_timing",
        homepage_total_ms=round((time.perf_counter() - total_started) * 1000, 2),
        stories_ms=section_timings.get("_fetch_stories_ms", 0),
        reels_ms=section_timings.get("_fetch_reels_ms", 0),
        live_rooms_ms=section_timings.get("_fetch_live_rooms_ms", 0),
        posts_ms=section_timings.get("_fetch_posts_ms", 0),
        profiles_ms=section_timings.get("profiles_ms", 0),
        cache_hit=False,
        section_cache_hits=section_cache_hits,
    )
    if elapsed_ms > _TOTAL_BUDGET_MS:
        payload["issues"].append(f"budget_exceeded: {elapsed_ms:.1f}ms")
        _log_outage_once(f"homepage budget exceeded: {elapsed_ms:.1f}ms")

    # Only cache if we got everything or if this is the async warm
    if (done_count == len(tasks) and not is_circuit_open()) or async_warm:
        set_cache(cache_key_str, payload, ttl=_CACHE_TTL_SECONDS)
        set_payload(payload, ttl=_CACHE_TTL_SECONDS)
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
    """Fetch sponsored/ad posts for homepage."""
    started = time.perf_counter()
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
        query = "SELECT " + ", ".join(cols) + " FROM chain_posts"
        if where:
            query += " WHERE " + " AND ".join(where)
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
    """Fetch nearby/trending users for homepage sidebar."""
    started = time.perf_counter()
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
        query = "SELECT " + ", ".join(cols) + " FROM chain_profiles"
        if where:
            query += " WHERE " + " AND ".join(where)
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


def get_homepage_data():
    from flask import session
    page_started = time.perf_counter()
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

    cached_full = None if has_session_profile else (get_full("public") or get_cache(full_cache_key))
    if cached_full is not None:
        log_info(
            "homepage_timing",
            homepage_total_ms=round((time.perf_counter() - page_started) * 1000, 2),
            stories_ms=0,
            reels_ms=0,
            live_rooms_ms=0,
            posts_ms=0,
            profiles_ms=0,
            cache_hit=True,
        )
        restore_timing_origin()
        return cached_full

    current = _safe_current_profile()
    public_data = copy.deepcopy(build_homepage_payload())
    if current and current.get("id"):
        own_rows = fetch_all(
            """
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
            """,
            (current["id"], current.get("auth_user_id")),
            timeout_ms=500,
        )
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
    local = local_content()
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
        local_stories = [_normalize_story(row, profile_map) for row in active_local_stories() if row.get("visibility", "public") == "public" or (current and row.get("profile_id") == current.get("id"))]
        seen = {row.get("id") for row in public_data.get("stories", [])}
        public_data["stories"] = [row for row in local_stories if row.get("id") not in seen] + public_data.get("stories", [])
    public_data["stats"]["posts"] = len(public_data.get("trending_posts", []))
    public_data["stats"]["reels"] = len(public_data.get("reels", []))
    public_data["stats"]["stories"] = len(public_data.get("stories", []))
    public_data["groups"] = _fetch_groups()
    public_data["sponsored_posts"] = _fetch_sponsored_posts()
    public_data["announcements"] = _fetch_announcements()
    public_data["nearby_users"] = _fetch_nearby_users(current)
    wallet = _wallet_snapshot(current)

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
    public_data["feed_live"] = _sort_live[:8]
    public_data["feed_reels"] = public_data.get("reels", [])[:8]
    public_data["feed_nearby"] = public_data.get("nearby_users", [])[:10]
    public_data["trending_profiles"] = public_data.get("recommended_profiles", [])[:5]
    public_data["following_count"] = (current or {}).get("following_count", 0)

    result = {
        "current": current,
        **public_data,
        "wallet": wallet,
        "hero_story_count": len(public_data["stories"]),
        "hero_live_count": len(public_data["live_rooms"]),
        "hero_profile_count": len(public_data["recommended_profiles"]),
        "hero_post_count": len(public_data["trending_posts"]),
        "missing_sources": public_data["issues"],
    }

    if not current:
        set_cache(full_cache_key, result, ttl=_CACHE_TTL_SECONDS)
        set_full("public", result, ttl=_CACHE_TTL_SECONDS)
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
    offset = max(0, (page - 1) * limit)
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
        has_more = len(items) >= limit
        return items[:limit], has_more
    except Exception:
        return [], False


def _normalize_items(rows, default_type="post"):
    """Normalize raw rows to feed item dicts with type tag."""
    result = []
    for r in (rows or []):
        if not r or not r.get("id"):
            continue
        item_type = r.get("_type") or r.get("type") or default_type
        normalized = {
            "id": str(r["id"]),
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
        placeholders = ",".join(f"'{uid}'" for uid in unique)
        rows = fast_query(
            f"SELECT id, username, display_name, full_name, avatar_url, is_verified, verified "
            f"FROM chain_profiles WHERE id IN ({placeholders})",
            timeout_ms=500, default=[]
        )
        return {str(r["id"]): r for r in rows if r.get("id")}
    except Exception:
        return {}


def _feed_for_you(profile_id=None, limit=20, offset=0):
    items = []
    seen = set()
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    if not cols:
        return items
    try:
        query = f"SELECT {', '.join(cols)} FROM chain_posts WHERE deleted_at IS NULL AND (visibility IS NULL OR visibility = 'public') ORDER BY created_at DESC LIMIT {limit + offset}"
        rows = fast_query(query, timeout_ms=800, default=[])
        for r in rows:
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
    pids = []
    for r in items:
        pids.append(r.get("profile_id"))
    pmap = _profile_map_for_ids(pids)
    result = []
    for r in items[offset:]:
        pid = r.get("profile_id")
        p = pmap.get(str(pid)) if pid else None
        if p:
            r["display_name"] = p.get("display_name") or p.get("full_name") or ""
            r["username"] = p.get("username") or ""
            r["avatar_url"] = p.get("avatar_url") or ""
            r["is_verified"] = p.get("is_verified") or p.get("verified") or False
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
        query = f"SELECT {', '.join(cols)} FROM chain_posts WHERE deleted_at IS NULL AND (visibility IS NULL OR visibility = 'public') ORDER BY created_at DESC LIMIT {limit + offset}"
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


def _feed_trending(profile_id=None, limit=20, offset=0):
    cols = _post_select() or ["id", "profile_id", "caption", "media_url", "likes_count", "comments_count", "created_at", "visibility", "video_url"]
    if not cols:
        return []
    try:
        query = f"SELECT {', '.join(cols)} FROM chain_posts WHERE deleted_at IS NULL ORDER BY (COALESCE(likes_count,0) + COALESCE(comments_count,0)) DESC LIMIT {limit + offset}"
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


def _feed_nearby(profile_id=None, limit=20, offset=0):
    try:
        rows = fast_query(
            "SELECT id, display_name, full_name, username, avatar_url, is_verified, verified, location, bio "
            "FROM chain_profiles WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT " + str(limit + offset),
            timeout_ms=500, default=[]
        )
    except Exception:
        rows = []
    result = []
    for r in rows[offset:]:
        result.append({
            "id": str(r["id"]),
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
        cols = ["id", "profile_id", "host_id", "creator_id", "title", "cover_url", "viewer_count", "category", "created_at"]
        rows = fast_query(
            f"SELECT {', '.join(cols)} FROM chain_live_rooms WHERE deleted_at IS NULL AND status = 'live' ORDER BY viewer_count DESC LIMIT {limit + offset}",
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
        pid = r.get("profile_id") or r.get("host_id") or r.get("creator_id")
        p = pmap.get(str(pid)) if pid else None
        title = r.get("title") or ""
        result.append({
            "id": str(r["id"]),
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
            "watch_url": f"/live/{r['id']}",
            "category": r.get("category") or "",
        })
    return result, len(result) >= limit


def _feed_reels(profile_id=None, limit=20, offset=0):
    from services.content_service import _reel_columns
    try:
        cols = ["id", "profile_id", "caption", "video_url", "thumbnail_url", "media_url", "likes_count", "comments_count", "view_count", "created_at"]
        query = f"SELECT {', '.join(cols)} FROM chain_reels WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT {limit + offset}"
        rows = fast_query(query, timeout_ms=500, default=[])
    except Exception:
        rows = []
    pids = [r.get("profile_id") for r in rows]
    pmap = _profile_map_for_ids(pids)
    result = []
    for r in rows[offset:]:
        pid = r.get("profile_id")
        p = pmap.get(str(pid)) if pid else None
        result.append({
            "id": str(r["id"]),
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
    return result, len(result) >= limit
