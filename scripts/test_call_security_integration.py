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

from services.env_service import get_env, load_project_env
from services.neon_service import _safe_optimize_dsn


def emit(status: str, stage: str, **payload) -> None:
    print(json.dumps({"status": status, "stage": stage, **payload}, sort_keys=True))


def _mask_host(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _host_fingerprint(host: str) -> str:
    import hashlib
    return hashlib.sha256((host or "").encode()).hexdigest()[:12]


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


def _insert_temp_block(cur, blocker_id: str, blocked_id: str) -> None:
    cur.execute(
        """
        INSERT INTO chain_blocks (blocker_profile_id, blocked_profile_id, created_at, deleted_at)
        VALUES (%s, %s, now(), NULL)
        ON CONFLICT DO NOTHING
        """,
        (blocker_id, blocked_id),
    )


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
    load_project_env()
    raw_dsn = (get_env("DATABASE_URL", "") or "").strip()
    canonical_dsn = _safe_optimize_dsn(raw_dsn) or raw_dsn
    selected_path = "canonical" if canonical_dsn and canonical_dsn != raw_dsn else "raw"
    host = _mask_host(canonical_dsn or raw_dsn)
    if not canonical_dsn:
        emit("BLOCKED_DATABASE_AUTH", "load_env", reason="DATABASE_URL missing", selected_path=selected_path)
        return 2

    try:
        socket.getaddrinfo(host, 5432, type=socket.SOCK_STREAM)
    except Exception as exc:
        emit("BLOCKED_DNS", "dns", host_fingerprint=_host_fingerprint(host), selected_path=selected_path, error_type=type(exc).__name__, message=str(exc)[:180])
        return 2

    import psycopg2

    marker = f"call-sec-{uuid4().hex}"
    started = time.perf_counter()
    try:
        conn = psycopg2.connect(canonical_dsn, connect_timeout=5)
    except Exception as exc:
        message = str(exc).lower()
        if "password" in message or "authentication" in message or "role" in message:
            status = "BLOCKED_DATABASE_AUTH"
        elif "ssl" in message or "tls" in message:
            status = "BLOCKED_TLS"
        elif "timeout" in message or "timed out" in message:
            status = "BLOCKED_TCP"
        else:
            status = "BLOCKED_TCP"
        emit(status, "connect", host_fingerprint=_host_fingerprint(host), selected_path=selected_path, error_type=type(exc).__name__, message=str(exc)[:180])
        return 2

    call_id = None
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 5000")
            cur.execute("SET lock_timeout = 2000")
            cur.execute("SELECT current_database(), current_user")
            db_name, db_user = cur.fetchone()
            emit("PASS", "connection", database=db_name, db_user=db_user, host_fingerprint=_host_fingerprint(host), selected_path=selected_path)

            _ensure_min_schema(cur)

            caller_id = str(uuid4())
            receiver_id = str(uuid4())
            blocked_id = str(uuid4())
            outsider_id = str(uuid4())

            _insert_temp_profile(cur, caller_id, "caller")
            _insert_temp_profile(cur, receiver_id, "receiver")
            _insert_temp_profile(cur, blocked_id, "blocked")
            _insert_temp_profile(cur, outsider_id, "outsider")
            _insert_temp_block(cur, caller_id, blocked_id)
            emit("PASS", "profiles_seeded", marker=marker, selected_path=selected_path)

            from services.webrtc_call_service import create_call, accept_call, reject_call, end_call, get_call, get_call_participants

            # unauthorized start must fail closed
            bad_self = create_call(caller_id, caller_id, call_type="audio")
            if bad_self.get("ok") or bad_self.get("error") != "self_call_not_allowed":
                emit("FAIL_APPLICATION", "self_call", result=bad_self, selected_path=selected_path)
                return 1
            emit("PASS", "self_call_rejected", selected_path=selected_path)

            # establish friendship gate required by the live call policy
            cur.execute(
                """
                INSERT INTO chain_friends (profile_id_1, profile_id_2, status, created_at, updated_at, deleted_at)
                VALUES (%s, %s, 'friend', now(), now(), NULL)
                ON CONFLICT DO NOTHING
                """,
                tuple(sorted((caller_id, receiver_id))) + tuple(),
            )
            conn.commit()
            emit("PASS", "friendship_seeded", selected_path=selected_path)

            call_result = create_call(caller_id, receiver_id, call_type="video")
            if not call_result.get("ok"):
                emit("FAIL_APPLICATION", "call_start", result=call_result, selected_path=selected_path)
                return 1
            call = call_result.get("call") or {}
            call_id = call.get("id")
            if not call_id:
                emit("FAIL_APPLICATION", "call_start_missing_id", result=call_result, selected_path=selected_path)
                return 1
            emit("PASS", "call_started", call_id=call_id, selected_path=selected_path)

            call_row = get_call(call_id)
            if not call_row or call_row.get("status") != "ringing":
                emit("FAIL_APPLICATION", "call_row", result=call_row, selected_path=selected_path)
                return 1
            emit("PASS", "call_row_present", selected_path=selected_path)

            unauthorized_accept = accept_call(call_id, outsider_id)
            if unauthorized_accept.get("ok") or unauthorized_accept.get("error") != "unauthorized":
                emit("FAIL_AUTHORIZATION", "unauthorized_accept", result=unauthorized_accept, selected_path=selected_path)
                return 1
            emit("PASS", "unauthorized_accept_rejected", selected_path=selected_path)

            accepted = accept_call(call_id, receiver_id)
            if not accepted.get("ok") or (accepted.get("call") or {}).get("status") != "accepted":
                emit("FAIL_APPLICATION", "accept_call", result=accepted, selected_path=selected_path)
                return 1
            emit("PASS", "receiver_accepts_call", selected_path=selected_path)

            participants = get_call_participants(call_id)
            if not any(str(p.get("profile_id")) == receiver_id and p.get("status") == "accepted" for p in participants):
                emit("FAIL_APPLICATION", "participant_accept_state", participants=participants, selected_path=selected_path)
                return 1
            emit("PASS", "participant_state_recorded", selected_path=selected_path)

            unauthorized_end = end_call(call_id, outsider_id)
            if unauthorized_end.get("ok") or unauthorized_end.get("error") != "unauthorized":
                emit("FAIL_AUTHORIZATION", "unauthorized_end", result=unauthorized_end, selected_path=selected_path)
                return 1
            emit("PASS", "non_participant_end_rejected", selected_path=selected_path)

            ended = end_call(call_id, caller_id)
            if not ended.get("ok") or (ended.get("call") or {}).get("status") != "ended":
                emit("FAIL_APPLICATION", "end_call", result=ended, selected_path=selected_path)
                return 1
            emit("PASS", "participant_end_accepted", selected_path=selected_path)

            blocked_call = create_call(caller_id, blocked_id, call_type="audio")
            if blocked_call.get("ok") or blocked_call.get("error") not in {"blocked", "friends_only", "receiver_busy", "Calling unavailable"}:
                emit("FAIL_AUTHORIZATION", "blocked_call", result=blocked_call, selected_path=selected_path)
                return 1
            emit("PASS", "blocked_relationship_rejected", selected_path=selected_path)

    except psycopg2.Error as exc:
        emit("FAIL_SCHEMA", "database", sqlstate=getattr(exc, "pgcode", None), message=str(exc).splitlines()[0][:180], selected_path=selected_path)
        return 1
    except Exception as exc:
        emit("FAIL_APPLICATION", "unexpected", error_type=type(exc).__name__, message=str(exc)[:180], selected_path=selected_path)
        return 1
    finally:
        with suppress(Exception):
            conn.rollback()
        with suppress(Exception):
            with conn.cursor() as cur:
                for table in ("chain_call_participants", "chain_calls", "chain_friends", "chain_blocks", "chain_profiles"):
                    if table == "chain_profiles":
                        cur.execute("DELETE FROM chain_profiles WHERE id IN (%s, %s, %s, %s)", (caller_id, receiver_id, blocked_id, outsider_id))
                    elif table == "chain_friends":
                        p1, p2 = sorted((caller_id, receiver_id))
                        cur.execute("DELETE FROM chain_friends WHERE profile_id_1 = %s AND profile_id_2 = %s", (p1, p2))
                    elif table == "chain_blocks":
                        cur.execute("DELETE FROM chain_blocks WHERE blocker_profile_id = %s AND blocked_profile_id = %s", (caller_id, blocked_id))
                    elif table == "chain_calls" and call_id:
                        cur.execute("DELETE FROM chain_calls WHERE id = %s", (call_id,))
                    elif table == "chain_call_participants" and call_id:
                        cur.execute("DELETE FROM chain_call_participants WHERE call_id = %s OR call_session_id = %s", (call_id, call_id))
            conn.commit()
        with suppress(Exception):
            conn.close()

    emit("PASS", "summary", elapsed_ms=round((time.perf_counter() - started) * 1000, 2), marker=marker, selected_path=selected_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
