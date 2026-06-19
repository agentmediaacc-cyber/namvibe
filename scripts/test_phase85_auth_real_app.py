#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
auth_files = list((ROOT / "templates/auth").glob("*.html"))
combined = "\n".join(path.read_text(errors="ignore") for path in auth_files)
auth_base = (ROOT / "templates/auth_minimal.html").read_text(errors="ignore") if (ROOT / "templates/auth_minimal.html").exists() else ""


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("auth templates exist", bool(auth_files))
check("mobile viewport exists", "viewport" in (combined + auth_base).lower())
check("no visible old chain branding", ">CHAIN<" not in combined and "Chain |" not in combined)
check("no fake helper/test accounts", "test helper" not in combined.lower() and "fake helper" not in combined.lower())
check("no hardcoded localhost visible", "localhost:" not in combined and "127.0.0.1:" not in combined)
check("login/register present", any("login" in p.name for p in auth_files) and any("register" in p.name for p in auth_files))
