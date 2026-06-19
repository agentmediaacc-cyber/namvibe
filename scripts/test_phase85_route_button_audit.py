#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase85_routes", ROOT / "scripts/phase85_route_button_audit.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

findings = mod.audit()
blockers = [f for f in findings if f[0] == "BLOCKER"]


def check(name, condition):
    if not condition:
        detail = "\n".join(f"{f[1]}:{f[2]} {f[3]} {f[4]}" for f in blockers[:20])
        raise AssertionError(f"{name}\n{detail}")
    print(f"PASS {name}")


check("route audit has no blockers", not blockers)
