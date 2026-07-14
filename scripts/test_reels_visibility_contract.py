#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
routes = (ROOT / "api_routes" / "reels_routes.py").read_text()
svc = (ROOT / "services" / "reels_service.py").read_text()


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}: {detail}")
        raise SystemExit(1)


check("visibility filter", "visibility = 'public'" in svc, "public filter missing")
check("cursor route", "invalid_cursor" in routes, "malformed cursor handling missing")
check("feed items alias", '"items": reels' in routes and '"reels": reels' in routes, "compat response missing")
print("OK")
