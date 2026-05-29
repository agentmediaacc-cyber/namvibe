import time
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from flask import has_request_context, session

from engines.cache_engine import cache_key, get_cache, set_cache
from services.request_cache import build_request_key, request_memoize
from services.neon_service import (
    fast_query,
    get_cached_table_columns,
    get_pool_status,
    get_tables_columns,
    is_circuit_open,
)
from services.profile_service import get_current_profile
from services.wallet_service import ensure_wallet


_CACHE_TTL_SECONDS = 30
_EMPTY_CACHE_TTL_SECONDS = 15
_QUERY_TIMEOUT_MS = 600
_TOTAL_BUDGET_MS = 700
_FAST_FALLBACK_MS = 400
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


def _log(message):
    print(f"[homepage_service] {message}")


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
        return _SCHEMA_CACHE.get(table_name, set())

    # 2. Lock for lookup
    with _SCHEMA_LOCK:
        # Re-check cache
        if _SCHEMA_CACHE and _SCHEMA_CACHE.get("_expires_at", 0) > now:
            return _SCHEMA_CACHE.get(table_name, set())

        # Initialize or refresh
        new_cache = {"_expires_at": now + 300} # Cache schema for 5 mins
        
        try:
            # Try local memory/filesystem cache first
            for name in _HOMEPAGE_TABLES:
                cached_columns = get_cached_table_columns(name)
                if cached_columns:
                    new_cache[name] = set(cached_columns)
            
            # If missing anything, try a quick DB lookup
            if len(new_cache) < len(_HOMEPAGE_TABLES) + 1: # +1 for _expires_at
                db_schemas = get_tables_columns(_HOMEPAGE_TABLES, timeout_ms=300)
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
        lambda: fast_query(sql_text, params=params or [], timeout_ms=timeout_ms, default=[]),
    )
    issue = f"{query_key}: unavailable" if not rows and get_pool_status().get("backoff_active") else None
    return rows, issue


def _profile_select():
    return _select_columns(
        "chain_profiles",
        [
            "id",
            "auth_user_id",
            "username",
            "display_name",
            "full_name",
            "avatar_url",
            "photo_url",
            "town",
            "city",
            "location",
            "region",
            "country",
            "country_origin",
            "current_location",
            "is_verified",
            "verified",
            "is_online",
            "is_creator",
            "creator_category",
            "dating_mode_enabled",
            "created_at",
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
    if "likes_count" in available:
        query += " ORDER BY likes_count DESC NULLS LAST, created_at DESC NULLS LAST"
    else:
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
    unique_ids = [profile_id for profile_id in dict.fromkeys(profile_ids) if profile_id]
    columns = _profile_select()
    if not unique_ids or not columns:
        return {}
    available = set(columns)
    placeholders = ", ".join(["%s"] * len(unique_ids))
    where = _build_where(available, [f"id IN ({placeholders})"])
    query = f"SELECT {', '.join(columns)} FROM chain_profiles WHERE {' AND '.join(where)}"
    rows, issue = _run_sql(f"profile_map:{len(unique_ids)}", query, unique_ids, timeout_ms=500)
    if issue:
        pass
    return {row.get("id"): _normalize_profile(row) for row in rows if row.get("id")}


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
        "likes_count": _safe_int(row.get("likes_count"), 0),
        "comments_count": _safe_int(row.get("comments_count"), 0),
        "category": _clean_text(row.get("category"), ""),
        "created_label": _format_relative(row.get("created_at")),
        "profile_url": profile.get("profile_url", "/discover/"),
    }


def _wallet_snapshot(current):
    snapshot = {"coin_balance": 0, "gift_earnings": 0, "label_balance": "0"}
    if not current:
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
        profile = get_current_profile()
        if profile:
            return profile
        auth_user_id = session.get("auth_user_id")
        if not auth_user_id:
            return None
        email = session.get("auth_email") or ""
        username = session.get("username") or (email.split("@")[0] if "@" in email else "chainuser")
        full_name = session.get("full_name") or username.replace("_", " ").title()
        return {
            "id": None,
            "auth_user_id": auth_user_id,
            "email": email,
            "username": username,
            "full_name": full_name,
            "display_name": full_name,
            "avatar_url": None,
            "profile_completed": False,
        }
    except Exception as error:
        _log(f"current profile unavailable: {error}")
        return None


def build_homepage_payload(async_warm=False):
    """Consolidated lightweight homepage payload builder with parallelization and tight budget."""
    cache_key_str = cache_key("chain_homepage_v3", "public")
    cached = get_cache(cache_key_str)
    if cached is not None:
        return cached

    payload = {
        "stories": [],
        "live_rooms": [],
        "recommended_profiles": [],
        "trending_posts": [],
        "dating_matches": [],
        "reels": [],
        "stats": {"stories": 0, "live_rooms": 0, "profiles": 0, "posts": 0, "reels": 0},
        "issues": [],
    }

    # Fast exit if Neon circuit is open
    if is_circuit_open():
        payload["issues"].append("neon: unavailable")
        return payload

    pool_status = get_pool_status()
    if not pool_status.get("recent_success") and not pool_status.get("pool_ready"):
        payload["issues"].append("neon: cold-start-pending")
        return payload

    started = time.perf_counter()
    
    def fetch_stories():
        cols = _story_select()
        if not cols: return []
        return fast_query(
            f"SELECT {', '.join(cols)} FROM chain_stories WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 12",
            timeout_ms=300
        )

    def fetch_live():
        cols = _live_select()
        if not cols: return []
        return fast_query(
            f"SELECT {', '.join(cols)} FROM chain_live_rooms WHERE (is_live = TRUE OR status = 'live') AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 8",
            timeout_ms=300
        )

    def fetch_profiles():
        cols = _profile_select()
        if not cols: return []
        return fast_query(
            f"SELECT {', '.join(cols)} FROM chain_profiles WHERE is_creator = TRUE AND deleted_at IS NULL ORDER BY created_at DESC LIMIT 10",
            timeout_ms=300
        )

    def fetch_posts():
        cols = _post_select()
        if not cols: return []
        return fast_query(
            f"SELECT {', '.join(cols)} FROM chain_posts WHERE deleted_at IS NULL ORDER BY likes_count DESC NULLS LAST, created_at DESC LIMIT 8",
            timeout_ms=300
        )

    def fetch_matches():
        cols = _profile_select()
        if not cols: return []
        return fast_query(
            f"SELECT {', '.join(cols)} FROM chain_profiles WHERE dating_mode_enabled = TRUE AND deleted_at IS NULL ORDER BY random() LIMIT 8",
            timeout_ms=300
        )

    def fetch_reels():
        cols = _reel_select()
        if not cols: return []
        return fast_query(
            f"SELECT {', '.join(cols)} FROM chain_reels WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 8",
            timeout_ms=300
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
    profile_map = _load_profile_map(profile_ids)

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
    if elapsed_ms > _TOTAL_BUDGET_MS:
        payload["issues"].append(f"budget_exceeded: {elapsed_ms:.1f}ms")
        _log_outage_once(f"homepage budget exceeded: {elapsed_ms:.1f}ms")

    # Only cache if we got everything or if this is the async warm
    if (done_count == len(tasks) and not is_circuit_open()) or async_warm:
        set_cache(cache_key_str, payload, ttl=_CACHE_TTL_SECONDS)
    elif "partial_fallback" in payload["issues"] or "neon: unavailable" in payload["issues"]:
        # Trigger async warm if we fell back
        _EXECUTOR.submit(build_homepage_payload, async_warm=True)

    return payload

def get_homepage_data():
    current = _safe_current_profile()
    public_data = build_homepage_payload()
    wallet = _wallet_snapshot(current)
    return {
        "current": current,
        **public_data,
        "wallet": wallet,
        "hero_story_count": len(public_data["stories"]),
        "hero_live_count": len(public_data["live_rooms"]),
        "hero_profile_count": len(public_data["recommended_profiles"]),
        "hero_post_count": len(public_data["trending_posts"]),
        "missing_sources": public_data["issues"],
    }
