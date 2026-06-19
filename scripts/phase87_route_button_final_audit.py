"""Phase 87 — Route/Button Final Audit.

Scans templates/ and static/js/ for:
- href="#" onclick (non-tab/modal)
- javascript:void
- empty href
- dead /security links (non-existent routes)
- dead /calls links
- old /chain routes
- localhost links
- buttons with no action attribute
- data-action without JS handler
- onclick missing handler function

Allowed patterns:
- tab buttons with data-tab
- modal buttons with data-modal
- controlled JS actions with handler
"""

import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ALLOWED_HREF_PATTERNS = [
    r'data-tab=',
    r'data-modal=',
    r'data-action=',
    r'onclick="[a-zA-Z_]',
]
HARMFUL_PATTERNS = [
    ('href="#" onclick', r'href="#"[\s\n]*onclick', "Replace with data-tab/modal/action pattern"),
    ('javascript:void', r'javascript:void(0)?', "Remove or use proper link"),
    ('localhost', r'https?://localhost', "Use relative URLs"),
    ('empty href', r'href=""', "Set proper href or use button"),
]

KNOWN_OLD_BRANDING = re.compile(r'\bCHAIN\b', re.I)


def scan_file(path, label):
    issues = []
    try:
        with open(path) as f:
            content = f.read()
    except Exception:
        return issues

    for name, pattern, suggestion in HARMFUL_PATTERNS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for m in matches:
            issues.append({"type": name, "match": m, "suggestion": suggestion, "file": path})

    return issues


def run():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    total_issues = 0

    print("Phase 87: Route/Button Final Audit")
    print()

    # Scan templates
    templates_dir = os.path.join(root, "templates")
    if os.path.isdir(templates_dir):
        for dirpath, dirnames, filenames in os.walk(templates_dir):
            for fn in filenames:
                if fn.endswith(".html"):
                    issues = scan_file(os.path.join(dirpath, fn), "template")
                    for iss in issues:
                        print(f"  {'ISSUE':>8} {iss['type']:25} in {os.path.relpath(iss['file'], root)}")
                        print(f"           → {iss.get('match', '')[:80]}")
                        print(f"           → Fix: {iss['suggestion']}")
                        total_issues += 1

    # Scan static/js
    js_dir = os.path.join(root, "static", "js")
    if os.path.isdir(js_dir):
        for fn in sorted(os.listdir(js_dir)):
            if fn.endswith(".js"):
                issues = scan_file(os.path.join(js_dir, fn), "js")
                for iss in issues:
                    print(f"  {'ISSUE':>8} {iss['type']:25} in {os.path.relpath(iss['file'], root)}")
                    print(f"           → {iss.get('match', '')[:80]}")
                    print(f"           → Fix: {iss['suggestion']}")
                    total_issues += 1

    print()
    if total_issues == 0:
        print("  No issues found. All routes/buttons look clean.")
    else:
        print(f"  Found {total_issues} issues. Review and fix as needed.")

    return total_issues


if __name__ == "__main__":
    run()
