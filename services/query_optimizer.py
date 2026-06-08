import threading
import time
from collections import deque

from services.logging_service import log_info, log_warning
from services.neon_service import fast_query


HOMEPAGE_QUERY_BUDGET_MS = {
    "stories": 100,
    "reels": 100,
    "live_rooms": 100,
    "posts": 200,
    "profiles": 200,
}

_PROFILE_LIMIT = 100
_QUERY_LOG = deque(maxlen=250)
_LOCK = threading.Lock()


def _clean_query(sql_text):
    return " ".join(str(sql_text or "").split())[:500]


def record_query(query, latency_ms, rows_returned, label=None, budget_ms=None):
    entry = {
        "ts": time.time(),
        "label": label or "query",
        "query": _clean_query(query),
        "latency_ms": round(float(latency_ms or 0), 2),
        "rows_returned": int(rows_returned or 0),
        "budget_ms": budget_ms,
        "slow": bool(budget_ms and latency_ms > budget_ms),
    }
    with _LOCK:
        _QUERY_LOG.appendleft(entry)
    log_info(
        "query_profile",
        label=entry["label"],
        latency_ms=entry["latency_ms"],
        rows_returned=entry["rows_returned"],
        query=entry["query"],
    )
    if entry["slow"]:
        log_warning(
            "homepage_query_budget_exceeded",
            label=entry["label"],
            latency_ms=entry["latency_ms"],
            budget_ms=budget_ms,
        )
    return entry


def profiled_query(label, sql_text, params=None, timeout_ms=1000, default=None, budget_ms=None):
    started = time.perf_counter()
    rows = fast_query(sql_text, params=params or [], timeout_ms=timeout_ms, default=default if default is not None else [])
    latency_ms = (time.perf_counter() - started) * 1000
    count = len(rows) if isinstance(rows, list) else (1 if rows else 0)
    record_query(sql_text, latency_ms, count, label=label, budget_ms=budget_ms)
    return rows


def batch_load_profiles(profile_ids, columns, build_where, normalize_profile, timeout_ms=200):
    unique_ids = [profile_id for profile_id in dict.fromkeys(profile_ids or []) if profile_id]
    unique_ids = unique_ids[:_PROFILE_LIMIT]
    if not unique_ids or not columns:
        return {}
    placeholders = ", ".join(["%s"] * len(unique_ids))
    where = build_where(set(columns), [f"id IN ({placeholders})"])
    query = f"SELECT {', '.join(columns)} FROM chain_profiles WHERE {' AND '.join(where)}"
    rows = profiled_query(
        "profiles",
        query,
        params=unique_ids,
        timeout_ms=timeout_ms,
        default=[],
        budget_ms=HOMEPAGE_QUERY_BUDGET_MS["profiles"],
    )
    return {row.get("id"): normalize_profile(row) for row in rows if row.get("id")}


def get_recent_queries(limit=100):
    with _LOCK:
        return list(_QUERY_LOG)[:limit]


def get_performance_summary():
    rows = get_recent_queries(250)
    by_label = {}
    for row in rows:
        label = row.get("label") or "query"
        bucket = by_label.setdefault(label, {"count": 0, "total_ms": 0.0, "max_ms": 0.0, "slow": 0})
        latency = float(row.get("latency_ms") or 0)
        bucket["count"] += 1
        bucket["total_ms"] += latency
        bucket["max_ms"] = max(bucket["max_ms"], latency)
        bucket["slow"] += 1 if row.get("slow") else 0
    for bucket in by_label.values():
        bucket["avg_ms"] = round(bucket["total_ms"] / bucket["count"], 2) if bucket["count"] else 0
        bucket["max_ms"] = round(bucket["max_ms"], 2)
        bucket.pop("total_ms", None)
    return {
        "budgets": HOMEPAGE_QUERY_BUDGET_MS,
        "total_profiled_queries": len(rows),
        "by_label": by_label,
        "recent_queries": rows[:50],
    }
