import os
import time
from typing import Dict, List, Set, Optional
from services.logging_service import log_info, log_error

# Global Schema Cache
_COLUMNS: Dict[str, Set[str]] = {}
_TABLES: Dict[str, bool] = {}
_WARMED = False

# Important tables to warm up at startup
CORE_TABLES = [
    "chain_profiles",
    "chain_posts",
    "chain_reels",
    "chain_status_posts",
    "chain_live_rooms",
    "chain_follows",
    "chain_blocks",
    "chain_notifications",
    "chain_message_threads",
    "chain_thread_members",
    "chain_messages",
    "chain_hashtags",
    "chain_presence",
    "chain_wallets",
    "chain_wallet_transactions",
    "chain_reports",
    "chain_spam_reports",
    "chain_content_quality_scores",
    "chain_search_history"
]

def warm_schema_cache():
    """
    Warms up the schema cache by querying all core tables at startup.
    This should be called once when the application starts.
    """
    global _WARMED
    if _WARMED:
        return
    
    log_info("schema_warming_started", count=len(CORE_TABLES))
    start_time = time.time()
    
    from services.neon_service import prime_schema_cache
    from services.supabase_safe import prime_supabase_schema
    
    # 1. Warm Neon Columns & existence
    try:
        prime_schema_cache(CORE_TABLES)
    except Exception as e:
        log_error("schema_warming_neon_failed", error=e)

    # 2. Warm Supabase Columns & existence
    try:
        prime_supabase_schema(CORE_TABLES)
    except Exception as e:
        log_error("schema_warming_supabase_failed", error=e)

    _WARMED = True
    duration = round((time.time() - start_time) * 1000, 2)
    log_info("schema_warming_completed", duration_ms=duration)

def get_columns(table: str) -> Set[str]:
    """Returns columns for a table from cache, or queries if not found (and logs miss)."""
    if table in _COLUMNS:
        return _COLUMNS[table]
    
    # If not warmed or not in core, we might still want to fetch it once
    # but the goal is to avoid this during requests.
    log_info("schema_cache_miss", table=table, kind="columns")
    
    from services.neon_service import get_table_columns
    cols = get_table_columns(table)
    if cols:
        _COLUMNS[table] = set(cols)
        return _COLUMNS[table]
    return set()

def is_table_active(table: str) -> bool:
    """Checks if a table exists from cache."""
    if table in _TABLES:
        return _TABLES[table]
    
    log_info("schema_cache_miss", table=table, kind="table_exists")
    
    from services.neon_service import table_exists
    exists = table_exists(table)
    _TABLES[table] = exists
    return exists

def reset_registry():
    global _WARMED, _COLUMNS, _TABLES
    _WARMED = False
    _COLUMNS = {}
    _TABLES = {}
