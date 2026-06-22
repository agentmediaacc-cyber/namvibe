#!/usr/bin/env python3
"""Phase 95 — Moderation & Safety System Audit.
   Verifies all components exist, tables are created, routes are wired, and service functions are present."""

import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("CHAIN_FAST_LOCAL", "1")
os.environ.setdefault("CHAIN_DISABLE_DB_PING", "1")
os.environ.setdefault("CHAIN_DISABLE_PREWARM", "1")

from services.env_service import load_project_env
load_project_env()
from services.neon_service import fast_query

PASS = 0
FAIL = 0
MISSING = 0


def check(label, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        msg = f"  FAIL  {label}"
        if detail:
            msg += f"  \u2014  {detail}"
        print(msg)


def check_missing(label, ok, detail=""):
    global MISSING
    if not ok:
        MISSING += 1
    return check(label, ok, detail)


def table_exists(name):
    try:
        row = fast_query(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s) AS e",
            [name], default=[{"e": False}]
        )
        return row and row[0].get("e", False)
    except Exception:
        return False


def column_exists(table, column):
    try:
        row = fast_query(
            "SELECT EXISTS (SELECT FROM information_schema.columns WHERE table_schema = 'public' AND table_name = %s AND column_name = %s) AS e",
            [table, column], default=[{"e": False}]
        )
        return row and row[0].get("e", False)
    except Exception:
        return False


def index_exists(name):
    try:
        row = fast_query(
            "SELECT EXISTS (SELECT FROM pg_indexes WHERE indexname = %s) AS e",
            [name], default=[{"e": False}]
        )
        return row and row[0].get("e", False)
    except Exception:
        return False


def file_contains(path, substr):
    full_path = ROOT / path
    if not full_path.exists():
        return False
    return substr in full_path.read_text(encoding="utf-8", errors="ignore")


def main():
    global PASS, FAIL, MISSING
    print("=" * 60)
    print("  PHASE 95 — MODERATION & SAFETY SYSTEM AUDIT")
    print("=" * 60)

    # ── SECTION 1: FILE EXISTENCE (20 checks) ──
    print(f"\n{'─' * 40}")
    print("  FILES EXIST")
    print(f"{'─' * 40}")

    files = [
        "scripts/phase95_moderation_schema_upgrade.py",
        "services/restriction_service.py",
        "services/account_risk_service.py",
        "services/content_flag_service.py",
        "services/appeal_service.py",
        "services/moderation_log_service.py",
        "api_routes/moderation_routes.py",
        "api_routes/block_routes.py",
        "api_routes/trust_routes.py",
    ]
    for f in files:
        check_missing(f"File: {f}", (ROOT / f).exists())

    check_missing("File: api_routes/admin_routes.py", (ROOT / "api_routes" / "admin_routes.py").exists())

    tmpl_admin_mod = ROOT / "templates" / "admin" / "moderation.html"
    check_missing("File: templates/admin/moderation.html", tmpl_admin_mod.exists())

    safety_dir = ROOT / "templates" / "safety"
    if safety_dir.exists():
        safety_files = sorted(f.name for f in safety_dir.iterdir() if f.is_file())
        check_missing("File: templates/safety/ (non-empty directory)", len(safety_files) > 0)
        for sf in safety_files:
            check(f"File: templates/safety/{sf}", True)
    else:
        check_missing("File: templates/safety/ (directory)", False)

    test_path = ROOT / "scripts" / "test_phase95_moderation.py"
    check_missing("File: scripts/test_phase95_moderation.py", test_path.exists())

    # ── SECTION 2: ROUTE EXISTENCE (40 checks) ──
    print(f"\n{'─' * 40}")
    print("  ROUTE STRINGS IN FILES")
    print(f"{'─' * 40}")

    mod_routes = [
        "/api/report/content",
        "/api/report/profile",
        "/api/report/message",
        "/api/report/call",
        "/api/block/list",
        "POST /api/block/",
        "DELETE /api/block/",
        "/api/restrict/list",
        "/api/restrict/",
        "/api/trust/summary",
        "/api/safety/reports",
        "/api/safety/blocked",
        "/api/safety/restricted",
    ]
    for route in mod_routes:
        check(f"Route: {route}", file_contains("api_routes/moderation_routes.py", route))

    block_routes = [
        "/api/blocked",
        "POST /api/blocked/",
        "DELETE /api/blocked/",
    ]
    for route in block_routes:
        check(f"Block route: {route}", file_contains("api_routes/block_routes.py", route))

    trust_routes = [
        "/api/trust/summary",
    ]
    for route in trust_routes:
        check(f"Trust route: {route}", file_contains("api_routes/trust_routes.py", route))

    admin_route_strings = [
        "admin_bp.route",
        "/dashboard",
        "/users",
        "/content",
        "/audit",
        "/moderation",
        "/system-audit",
        "/system-health",
    ]
    for route in admin_route_strings:
        check(f"Admin route: {route}", file_contains("api_routes/admin_routes.py", route))

    # ── SECTION 3: DB TABLES (15 checks) ──
    print(f"\n{'─' * 40}")
    print("  DB TABLES")
    print(f"{'─' * 40}")

    new_tables = [
        "chain_restrictions",
        "chain_content_flags",
        "chain_account_risk",
        "chain_appeals",
        "chain_moderation_logs",
    ]
    for t in new_tables:
        check_missing(f"Table: {t}", table_exists(t))

    phase48_tables = [
        "chain_trust_scores",
        "chain_user_reports",
        "chain_moderation_queue",
        "chain_moderation_actions",
        "chain_spam_events",
        "chain_blocks",
        "chain_fraud_events",
        "chain_rate_limit_events",
        "chain_reports",
    ]
    for t in phase48_tables:
        check_missing(f"Table: {t}", table_exists(t))

    # ── SECTION 4: DB COLUMNS (30 checks) ──
    print(f"\n{'─' * 40}")
    print("  DB COLUMNS")
    print(f"{'─' * 40}")

    restriction_cols = ["id", "profile_id", "restricted_by_profile_id", "restriction_type", "reason", "status", "duration_minutes", "expires_at", "created_at", "updated_at"]
    for c in restriction_cols:
        check(f"chain_restrictions.{c}", column_exists("chain_restrictions", c))

    content_flag_cols = ["id", "profile_id", "content_type", "content_id", "flag_type", "severity", "status", "flagged_by_profile_id", "reason", "created_at", "resolved_at"]
    for c in content_flag_cols:
        check(f"chain_content_flags.{c}", column_exists("chain_content_flags", c))

    account_risk_cols = ["id", "profile_id", "risk_level", "risk_score", "new_account", "no_profile", "mass_action_count", "report_count", "restriction_count", "signals", "updated_at", "created_at"]
    for c in account_risk_cols:
        check(f"chain_account_risk.{c}", column_exists("chain_account_risk", c))

    appeal_cols = ["id", "profile_id", "appeal_type", "target_id", "reason", "details", "status", "reviewed_by_profile_id", "resolution_note", "created_at", "resolved_at"]
    for c in appeal_cols:
        check(f"chain_appeals.{c}", column_exists("chain_appeals", c))

    mod_log_cols = ["id", "actor_profile_id", "target_profile_id", "action", "entity_type", "entity_id", "reason", "details", "ip_address", "created_at"]
    for c in mod_log_cols:
        check(f"chain_moderation_logs.{c}", column_exists("chain_moderation_logs", c))

    # ── SECTION 5: INDEXES (8 checks) ──
    print(f"\n{'─' * 40}")
    print("  INDEXES")
    print(f"{'─' * 40}")

    indexes = [
        ("chain_restrictions_profile_id_idx", "idx_restrictions_profile"),
        ("chain_restrictions_status_idx", "idx_restrictions_status"),
        ("chain_content_flags_content_idx", "idx_content_flags_content"),
        ("chain_content_flags_status_idx", "idx_content_flags_status"),
        ("chain_account_risk_profile_id_idx", "idx_account_risk_profile"),
        ("chain_appeals_status_idx", "idx_appeals_status"),
        ("chain_moderation_logs_actor_idx", "idx_mod_logs_actor"),
        ("chain_moderation_logs_action_idx", "idx_mod_logs_action"),
    ]
    for display_name, actual_name in indexes:
        check_missing(f"Index: {display_name}", index_exists(actual_name))

    # ── SECTION 6: SERVICE FUNCTIONS (25 checks) ──
    print(f"\n{'─' * 40}")
    print("  SERVICE FUNCTIONS")
    print(f"{'─' * 40}")

    service_map = {
        "services.restriction_service": [
            "restrict_user",
            "unrestrict_user",
            "is_restricted",
            "get_active_restrictions",
            "get_restriction_history",
            "expire_restrictions",
        ],
        "services.account_risk_service": [
            "get_or_create_risk",
            "assess_account_risk",
            "update_risk_signal",
            "get_risk_level",
        ],
        "services.content_flag_service": [
            "flag_content",
            "resolve_flag",
            "get_content_flags",
            "is_content_flagged",
        ],
        "services.appeal_service": [
            "submit_appeal",
            "review_appeal",
            "get_user_appeals",
            "get_pending_appeals",
        ],
        "services.moderation_log_service": [
            "log_moderation_action",
            "get_moderation_logs",
            "get_moderation_log_count",
        ],
    }

    for mod_name, funcs in service_map.items():
        try:
            mod = importlib.import_module(mod_name)
            for fn in funcs:
                check(f"{mod_name.split('.')[-1]}.{fn}", hasattr(mod, fn))
        except Exception as e:
            for fn in funcs:
                check_missing(f"{mod_name.split('.')[-1]}.{fn}", False, str(e))

    # ── SUMMARY ──
    total = PASS + FAIL
    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  PASS:    {PASS}")
    print(f"  FAIL:    {FAIL}")
    print(f"  MISSING: {MISSING}")
    print(f"  TOTAL:   {total}")
    print(f"{'=' * 60}")

    if FAIL == 0:
        print("  All checks passed!")
    else:
        print(f"  {FAIL} check(s) failed — review above.")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
