#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = (ROOT / "templates/base.html").read_text()
home_css = (ROOT / "static/css/home_modern_clean.css").read_text()
home = (ROOT / "templates/chain_home.html").read_text()


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


check("base does not render floating create shortcut", "class=\"app-floating-create\"" not in base)
check("home clean css is included", "home_modern_clean.css" in home)
check("floating shortcut class is force hidden as safety", ".app-floating-create" in home_css and "display: none !important" in home_css)
check("floating shortcut cannot cover feed", "pointer-events: none" in home_css)
check("no global install shortcut in base", "beforeinstallprompt" not in base.lower())
