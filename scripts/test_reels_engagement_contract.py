#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
svc = (ROOT / "services" / "engagement_service.py").read_text()


def check(name, cond, detail=""):
    if cond:
        print(f"PASS {name}")
    else:
        print(f"FAIL {name}: {detail}")
        raise SystemExit(1)


check("reel reactions table", "chain_reel_reactions" in svc, "missing reel likes table")
check("saved items table", "chain_saved_items" in svc, "missing save table")
check("like notifications", '"reel_like"' in svc, "missing reel like event")
check("save toggle present", "def toggle_save" in svc, "missing save toggle")
print("OK")
