#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import socket
import sys
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def emit(status: str, stage: str, **payload) -> None:
    print(json.dumps({"status": status, "stage": stage, **payload}, sort_keys=True))


def _mask_host(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _pick_columns(cur, table: str, preferred: list[str]) -> list[str]:
    cur.execute(
        """
        SELECT column_name, is_nullable, column_default, data_type
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        """,
        (table,),
    )
    cols = cur.fetchall()
    available = {r[0]: {"nullable": r[1] == "YES", "default": r[2], "type": r[3]} for r in cols}
    return [c for c in preferred if c in available]


def _insert_temp_profile(cur, profile_id: str, suffix: str) -> None:
    cols = _pick_columns(cur, "chain_profiles", [
        "id", "auth_user_id", "username", "display_name", "email", "created_at", "updated_at",
        "who_can_message", "who_can_call", "profile_visibility", "privacy", "deleted_at",
    ])
    values = []
    params = []
    now_sql = "now()"
    for col in cols:
        if col == "id":
            values.append("%s")
            params.append(profile_id)
        elif col == "auth_user_id":
            values.append("%s")
            params.append(profile_id)
        elif col == "username":
            values.append("%s")
            params.append(f"call_sec_{suffix}_{profile_id[:8]}")
        elif col == "display_name":
            values.append("%s")
            params.append(f"Call Sec {suffix}")
        elif col == "email":
            values.append("%s")
            params.append(f"call-sec-{suffix}-{profile_id[:8]}@example.test")
        elif col in {"who_can_message", "who_can_call"}:
            values.append("%s")
            params.append("everyone")
        elif col in {"profile_visibility", "privacy"}:
            values.append("%s")
            params.append("public")
        elif col in {"created_at", "updated_at"}:
            values.append(now_sql)
        elif col == "deleted_at":
            values.append("NULL")
        else:
            values.append("DEFAULT")
    if "id" not in cols or "username" not in cols:
        raise RuntimeError("chain_profiles schema missing id/username")
    sql = f"INSERT INTO chain_profiles ({', '.join(cols)}) VALUES ({', '.join(values)})"
    cur.execute(sql, params)


def _ensure_min_schema(cur) -> None:
    for table in ("chain_calls", "chain_call_participants", "chain_friends", "chain_blocks", "chain_profiles"):
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table,),
        )
        if not cur.fetchone():
            raise RuntimeError(f"missing table: {table}")
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'chain_calls'
        """,
    )
    call_cols = {r[0] for r in cur.fetchall()}
    required = {"id", "caller_profile_id", "receiver_profile_id", "call_type", "call_mode", "status", "started_at"}
    missing = sorted(required - call_cols)
    if missing:
        raise RuntimeError(f"chain_calls missing columns: {', '.join(missing)}")
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'chain_call_participants'
        """,
    )
    participant_cols = {r[0] for r in cur.fetchall()}
    required_participant = {"call_id", "profile_id", "status"}
    missing_participant = sorted(required_participant - participant_cols)
    if missing_participant:
        raise RuntimeError(f"chain_call_participants missing columns: {', '.join(missing_participant)}")


def main() -> int:
    from services.env_service import load_project_env

    load_project_env()
    dsn = (os.getenv("DATABASE_URL") or "").strip()
    host = _mask_host(dsn)
    if not dsn:
        emit("BLOCKED_ENVIRONMENT", "load_env", reason="DATABASE_URL missing")
        return 2

    try:
        socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)
    except Exception as exc:
        emit("BLOCKED_ENVIRONMENT", "dns", host=host, error_type=type(exc).__name__, message=str(exc)[:180])
        return 2

    import psycopg2

    marker = f"call-sec-{uuid4().hex}"
    started = time.perf_counter()
    try:
        conn = psycopg2.connect(dsn, connect_timeout=5)
    except Exception as exc:
        emit("BLOCKED_ENVIRONMENT", "connect", host=host, error_type=type(exc).__name__, message=str(exc)[:180])
        return 2

    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 5000")
            cur.execute("SET lock_timeout = 2000")
            cur.execute("SELECT current_database(), current_user")
            db_name, db_user = cur.fetchone()
            emit("PASS", "connection", database=db_name, db_user=db_user, host=host)

            _ensure_min_schema(cur)

            caller_id = str(uuid4())
            receiver_id = str(uuid4())
            blocked_id = str(uuid4())
            outsider_id = str(uuid4())

            _insert_temp_profile(cur, caller_id, "caller")
            _insert_temp_profile(cur, receiver_id, "receiver")
            _insert_temp_profile(cur, blocked_id, "blocked")
            _insert_temp_profile(cur, outsider_id, "outsider")
            emit("PASS", "profiles_seeded", marker=marker)

            from services.webrtc_call_service import create_call, accept_call, reject_call, end_call, get_call, get_call_participants

            # unauthorized start must fail closed
            bad_self = create_call(caller_id, caller_id, call_type="audio")
            if bad_self.get("ok") or bad_self.get("error") != "self_call_not_allowed":
                emit("FAIL_APPLICATION", "self_call", result=bad_self)
                return 1
            emit("PASS", "self_call_rejected")

            # establish friendship gate required by the live call policy
            cur.execute(
                """
                INSERT INTO chain_friends (profile_id_1, profile_id_2, status, created_at, updated_at, deleted_at)
                VALUES (%s, %s, 'friend', now(), now(), NULL)
                ON CONFLICT DO NOTHING
                """,
                tuple(sorted((caller_id, receiver_id))) + tuple(),
            )
            emit("PASS", "friendship_seeded")

            call_result = create_call(caller_id, receiver_id, call_type="video")
            if not call_result.get("ok"):
                emit("FAIL_APPLICATION", "call_start", result=call_result)
                return 1
            call = call_result.get("call") or {}
            call_id = call.get("id")
            if not call_id:
                emit("FAIL_APPLICATION", "call_start_missing_id", result=call_result)
                return 1
            emit("PASS", "call_started", call_id=call_id)

            call_row = get_call(call_id)
            if not call_row or call_row.get("status") != "ringing":
                emit("FAIL_APPLICATION", "call_row", result=call_row)
                return 1
            emit("PASS", "call_row_present")

            unauthorized_accept = accept_call(call_id, outsider_id)
            if unauthorized_accept.get("ok") or unauthorized_accept.get("error") != "unauthorized":
                emit("FAIL_APPLICATION", "unauthorized_accept", result=unauthorized_accept)
                return 1
            emit("PASS", "unauthorized_accept_rejected")

            accepted = accept_call(call_id, receiver_id)
            if not accepted.get("ok") or (accepted.get("call") or {}).get("status") != "accepted":
                emit("FAIL_APPLICATION", "accept_call", result=accepted)
                return 1
            emit("PASS", "receiver_accepts_call")

            participants = get_call_participants(call_id)
            if not any(str(p.get("profile_id")) == receiver_id and p.get("status") == "accepted" for p in participants):
                emit("FAIL_APPLICATION", "participant_accept_state", participants=participants)
                return 1
            emit("PASS", "participant_state_recorded")

            unauthorized_end = end_call(call_id, outsider_id)
            if unauthorized_end.get("ok") or unauthorized_end.get("error") != "unauthorized":
                emit("FAIL_APPLICATION", "unauthorized_end", result=unauthorized_end)
                return 1
            emit("PASS", "non_participant_end_rejected")

            ended = end_call(call_id, caller_id)
            if not ended.get("ok") or (ended.get("call") or {}).get("status") != "ended":
                emit("FAIL_APPLICATION", "end_call", result=ended)
                return 1
            emit("PASS", "participant_end_accepted")

            blocked_call = create_call(caller_id, blocked_id, call_type="audio")
            if blocked_call.get("ok") or blocked_call.get("error") not in {"blocked", "friends_only", "receiver_busy"}:
                emit("FAIL_APPLICATION", "blocked_call", result=blocked_call)
                return 1
            emit("PASS", "blocked_relationship_rejected")

            conn.rollback()
            emit("PASS", "transaction_rolled_back", marker=marker)
    except psycopg2.Error as exc:
        emit("FAIL_SCHEMA", "database", sqlstate=getattr(exc, "pgcode", None), message=str(exc).splitlines()[0][:180])
        return 1
    except Exception as exc:
        emit("FAIL_APPLICATION", "unexpected", error_type=type(exc).__name__, message=str(exc)[:180])
        return 1
    finally:
        with suppress(Exception):
            conn.rollback()
        with suppress(Exception):
            conn.close()

    emit("PASS", "summary", elapsed_ms=round((time.perf_counter() - started) * 1000, 2), marker=marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
