#!/usr/bin/env python3
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "templates"


def check(name, ok, detail=""):
    print(("PASS" if ok else "FAIL") + f": {name}" + (f" - {detail}" if detail else ""))
    if not ok:
        raise AssertionError(name)


def main():
    templates = list(TEMPLATE_ROOT.rglob("*.html"))
    visible = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in templates)
    check("visible templates use NamVibe", "NamVibe" in visible)
    title_chain = [
        str(path.relative_to(ROOT))
        for path in templates
        if re.search(r"{%\s*block\s+title\s*%}[^%]*\bCHAIN\b", path.read_text(encoding="utf-8", errors="ignore"))
    ]
    check("no public template title says CHAIN", not title_chain, ", ".join(title_chain[:8]))
    check("navbar brand says NamVibe", "social-top-brand" in visible and "NamVibe" in visible)
    check("homepage brand says NamVibe", "NamVibe" in (ROOT / "templates" / "chain_home.html").read_text(encoding="utf-8", errors="ignore"))
    check("login/register pages say NamVibe", all("NamVibe" in (ROOT / "templates" / "auth" / name).read_text(encoding="utf-8", errors="ignore") for name in ("login.html", "register.html")))
    check("metadata says NamVibe", "NamVibe" in (ROOT / "templates" / "base.html").read_text(encoding="utf-8", errors="ignore"))
    backend = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "services").glob("*.py"))
    check("internal chain_ table references are allowed", "chain_profiles" in backend)
    check("backend may still use CHAIN for internal env/config", "CHAIN_" in backend or "CHAIN_" in (ROOT / "app.py").read_text(encoding="utf-8", errors="ignore"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
