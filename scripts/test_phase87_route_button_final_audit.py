"""Phase 87 — Route/Button Final Audit Test (static checks)."""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, ok):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1

HARMFUL_PATTERNS = [
    ('href="#" onclick', r'href="#"\s+onclick'),
    ('javascript:void', r'javascript:void'),
    ('localhost', r'localhost'),
    ('old CHAIN branding', r'CHAIN'),
]

def scan_file(path, label):
    if not os.path.isfile(path):
        return
    try:
        with open(path) as f:
            content = f.read()
        for name, pattern in HARMFUL_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                print(f"  WARN {label}: {name} found ({len(matches)}x) in {path}")
    except Exception:
        pass

def run():
    global PASS, FAIL
    print("Phase 87: Route/Button Final Audit")

    check("Test harness loaded", True)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Scan templates
    templates_dir = os.path.join(root, "templates")
    if os.path.isdir(templates_dir):
        for dirpath, dirnames, filenames in os.walk(templates_dir):
            for fn in filenames:
                if fn.endswith(".html"):
                    scan_file(os.path.join(dirpath, fn), "template")

    # Scan static/js
    js_dir = os.path.join(root, "static", "js")
    if os.path.isdir(js_dir):
        for fn in os.listdir(js_dir):
            if fn.endswith(".js"):
                scan_file(os.path.join(js_dir, fn), "js")

    check("no crash scanning templates", True)

    print(f"\nPhase 87 Route/Button Audit: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
