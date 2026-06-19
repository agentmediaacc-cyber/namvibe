#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
auth_templates = list((ROOT / "templates/auth").glob("*.html"))
base_auth = (ROOT / "templates/auth_minimal.html").read_text() if (ROOT / "templates/auth_minimal.html").exists() else ""
combined = "\n".join(path.read_text() for path in auth_templates)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("auth templates exist", bool(auth_templates))
check("mobile viewport configured", "viewport" in base_auth.lower() or "viewport" in combined.lower())
check("login route is present", any("login" in path.name for path in auth_templates))
check("register route is present", any("register" in path.name for path in auth_templates))
check("no visible fake helper on login/register", "test helper" not in combined.lower() and "fake helper" not in combined.lower())
check("no hardcoded localhost in auth", "localhost:" not in combined)
check("no old visible CHAIN branding", ">CHAIN<" not in combined and "Chain |" not in combined)
