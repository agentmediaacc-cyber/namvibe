#!/usr/bin/env python3
import os
import socket
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.env_service import load_project_env


load_project_env()


def emit(status, name, detail=""):
    print(f"{status} [{name}] {detail}")
    return status == "PASS"


def parsed_database_url():
    raw = (os.getenv("DATABASE_URL") or "").strip()
    return raw, urlparse(raw) if raw else None


def main():
    raw, parsed = parsed_database_url()
    host = parsed.hostname if parsed else None
    emit("PASS" if host else "FAIL", "database_host", host or "DATABASE_URL missing")
    if not host:
        print("FAIL")
        return 1

    dns_ok = False
    try:
        infos = socket.getaddrinfo(host, parsed.port or 5432, proto=socket.IPPROTO_TCP)
        addrs = sorted({info[4][0] for info in infos})
        dns_ok = True
        emit("PASS", "dns_resolution", ", ".join(addrs[:3]))
    except Exception as error:
        emit("FAIL", "dns_resolution", str(error))

    psycopg_ok = False
    try:
        import psycopg2

        connect_timeout = 5
        conn = psycopg2.connect(raw, connect_timeout=connect_timeout)
        try:
            psycopg_ok = True
            emit("PASS", "psycopg_connect", "connected")
            with conn.cursor() as cursor:
                cursor.execute("SELECT now()")
                row = cursor.fetchone()
            emit("PASS" if row else "FAIL", "select_now", str(row[0]) if row else "empty result")
        finally:
            conn.close()
    except Exception as error:
        emit("FAIL", "psycopg_connect", str(error))

    ok = dns_ok and psycopg_ok
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
