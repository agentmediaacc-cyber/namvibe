#!/usr/bin/env python3
"""Verify premium UI palette and absence of pink tokens."""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

SCAN_DIRS = [ROOT / "static/css", ROOT / "templates", ROOT / "static/js"]
EXCLUDE_PARTS = {"static/uploads", "__pycache__", "templates/dev"}

PINK_PATTERNS = [
    re.compile(pattern, re.I)
    for pattern in [
        r"\bpink\b",
        r"\brose\b",
        r"\bfuchsia\b",
        r"#ec4899",
        r"#f472b6",
        r"#db2777",
        r"#be185d",
        r"#ff4da6",
        r"#ff2d95",
        r"#ff0050",
        r"#e6005c",
        r"#ff4080",
        r"#ff2f7d",
        r"#e1306c",
        r"#d41472",
        r"#d946ef",
        r"rgba\(\s*255\s*,\s*0\s*,\s*80",
        r"rgba\(\s*230\s*,\s*0\s*,\s*92",
        r"rgba\(\s*255\s*,\s*47\s*,\s*125",
        r"rgba\(\s*255\s*,\s*77\s*,\s*109",
    ]
]


def iter_scan_files():
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in {".css", ".html", ".js"}:
                continue
            rel = path.relative_to(ROOT).as_posix()
            if any(part in rel for part in EXCLUDE_PARTS):
                continue
            yield path


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def check(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"{status}: {name}" + (f" - {detail}" if detail else ""))
    return bool(condition)


def main():
    failures = 0
    offenders = []
    for path in iter_scan_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PINK_PATTERNS:
            match = pattern.search(text)
            if match:
                offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)}")
                break

    failures += not check("no pink/rose/fuchsia tokens in CSS/templates/JS", not offenders, "; ".join(offenders[:20]))

    homepage_css = read("static/css/homepage_premium.css")
    required_palette = {
        "--chain-bg: #f8fafc",
        "--chain-surface: #ffffff",
        "--chain-surface-soft: #f1f5f9",
        "--chain-text: #0f172a",
        "--chain-muted: #64748b",
        "--chain-border: #e2e8f0",
        "--chain-primary: #2563eb",
        "--chain-primary-dark: #1d4ed8",
        "--chain-accent: #06b6d4",
        "--chain-premium: #f59e0b",
        "--chain-success: #16a34a",
        "--chain-danger: #dc2626",
    }
    missing_palette = [token for token in sorted(required_palette) if token not in homepage_css]
    failures += not check("homepage CSS uses premium palette variables", not missing_palette, ", ".join(missing_palette))

    sys.path.insert(0, str(ROOT))
    try:
        from app import app
        with app.test_client() as client:
            response = client.get("/", follow_redirects=False)
            failures += not check("homepage route renders", response.status_code in {200, 302}, str(response.status_code))
    except Exception as exc:
        failures += not check("homepage route renders", False, str(exc))

    chain_home = read("templates/chain_home.html")
    class_values = re.findall(r'class="([^"]*)"', chain_home)
    class_sets = [set(value.split()) for value in class_values]
    left_navs = sum(1 for classes in class_sets if "home-left-rail" in classes)
    bottom_navs = sum(1 for classes in class_sets if "mobile-bottom-nav" in classes)
    failures += not check("homepage has no duplicate nav", left_navs <= 1 and bottom_navs <= 1, f"left={left_navs}, bottom={bottom_navs}")
    loose_icon_fragments = [fragment for fragment in (">i<", ">I<", ">fa-<", "</i> <i") if fragment in chain_home]
    failures += not check("homepage has no loose broken letters/icons", not loose_icon_fragments, ", ".join(loose_icon_fragments))

    readable_classes = ("post-author-name", "post-caption", "feed-tab", "composer-card", "story-card", "reel-card", "live-card")
    missing_readable = [name for name in readable_classes if name not in homepage_css and name not in chain_home]
    failures += not check("feed cards have readable text classes", not missing_readable, ", ".join(missing_readable))
    failures += not check("mobile responsive CSS exists", "@media" in homepage_css and ("max-width: 768px" in homepage_css or "max-width: 900px" in homepage_css))

    profile_css = read("static/css/profile_premium.css") + "\n" + read("static/css/profile.css") + "\n" + read("static/css/chain_profile.css")
    profile_offenders = [pattern.pattern for pattern in PINK_PATTERNS if pattern.search(profile_css)]
    failures += not check("profile CSS has no pink tokens", not profile_offenders, ", ".join(profile_offenders[:8]))
    profile_required = ("--profile-surface", "--profile-ink", "--profile-primary", "profile-empty-card", "@media")
    missing_profile = [token for token in profile_required if token not in profile_css]
    failures += not check("profile page keeps readable premium styling", not missing_profile, ", ".join(missing_profile))

    if failures:
        print(f"FAIL: {failures} premium UI checks failed")
        return 1
    print("PASS: no pink premium UI checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
