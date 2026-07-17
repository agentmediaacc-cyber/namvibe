#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.neon_service import fast_query, table_exists

TABLES = [
    "chain_dating_profiles",
    "chain_dating_preferences",
    "chain_dating_likes",
    "chain_dating_matches",
    "chain_dating_blocks",
    "chain_dating_reports",
    "chain_cy_enrollments",
    "chain_cy_matches",
    "chain_cy_introductions",
]


def safe_query(sql, params=()):
    try:
        return fast_query(sql, params, timeout_ms=5000, default=[])
    except Exception as exc:
        return {"error": type(exc).__name__, "message": str(exc)[:120]}


def main():
    summary = []
    for table in TABLES:
        exists = table_exists(table)
        columns = []
        indexes = []
        pk = []
        rows = []
        if exists:
            columns = safe_query(
                """
                SELECT column_name, data_type, is_nullable, column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
                """,
                (table,),
            ) or []
            indexes = safe_query(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = %s
                ORDER BY indexname
                """,
                (table,),
            ) or []
            pk = safe_query(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.table_name = %s AND tc.constraint_type = 'PRIMARY KEY'
                ORDER BY kcu.ordinal_position
                """,
                (table,),
            ) or []
            rows = safe_query(f"SELECT COUNT(*) AS count FROM {table}", ()) or []
        print(json.dumps({
            "table": table,
            "exists": exists,
            "columns": columns,
            "primary_key": pk,
            "indexes": indexes,
            "row_count": rows[0]["count"] if rows else None,
            "schema_dependency": "CONFIRMED" if exists and columns else "MISSING",
        }, default=str))


if __name__ == "__main__":
    main()
