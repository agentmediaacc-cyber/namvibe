#!/usr/bin/env python3
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("phase85_audit", ROOT / "scripts/phase85_audit_fake_placeholders.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

findings = mod.scan()
blockers = [f for f in findings if f["severity"] == "BLOCKER"]
allowed = []


def check(name, condition):
    if not condition:
        detail = "\n".join(f"{f['path']}:{f['line']} {f['term']} {f['snippet']}" for f in blockers[:20])
        raise AssertionError(f"{name}\n{detail}")
    print(f"PASS {name}")


check("audit script returns findings list", isinstance(findings, list))
check("no production-facing fake/placeholder blockers", not blockers)
