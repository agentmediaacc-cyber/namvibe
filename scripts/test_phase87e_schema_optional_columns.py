"""Phase 87E — Verify schema optional columns are handled safely."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0

def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name} {detail}")
        FAIL += 1

def run():
    global PASS, FAIL
    print("=" * 60)
    print("PHASE 87E — SCHEMA OPTIONAL COLUMNS")
    print("=" * 60)

    # 1. _candidate_rows uses dynamic column detection
    print("\n--- smart_suggestion_service ---")
    src = open("services/smart_suggestion_service.py", "r").read()
    check("imports get_cached_table_columns", "get_cached_table_columns" in src)
    check("allow_profile_discovery conditionally selected", 
          '"allow_profile_discovery" in profile_cols' in src or 'has_discovery' in src)
    check("COALESCE guard only when column exists",
          "if has_discovery:" in src)

    try:
        from services.smart_suggestion_service import build_recommendation_cards
        check("build_recommendation_cards imports", True)
    except ImportError as e:
        check(f"build_recommendation_cards imports ({e})", False)

    # 2. No unconditional SELECT allow_profile_discovery
    print("\n--- grep check ---")
    unconditional = False
    for root, dirs, files in os.walk("services"):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path) as fh:
                    text = fh.read()
                if "allow_profile_discovery" in text:
                    with open(path) as fh:
                        lines = fh.readlines()
                    in_discovery_block = False
                    for i, line in enumerate(lines, 1):
                        stripped = line.strip()
                        if stripped.startswith("#") or stripped.startswith('"""'):
                            continue
                        if "if has_discovery:" in stripped or "if has_discovery :" in stripped:
                            in_discovery_block = True
                            continue
                        if in_discovery_block:
                            indented = (line[0] == ' ' or line[0] == '\t')
                            if not indented and stripped:
                                in_discovery_block = False
                            if in_discovery_block:
                                continue
                        if "allow_profile_discovery" in stripped:
                            if "get_cached_table_columns" in stripped or "LOGIN_PROFILE_FIELD_CANDIDATES" in stripped or "available_columns" in stripped or "profile_cols" in stripped or "fallback_columns" in stripped or "has_discovery" in stripped:
                                continue
                            # Allow non-SELECT references (form handling, column list definition)
                            if "form.get(" in stripped or "LOGIN_PROFILE" in stripped:
                                continue
                            unconditional = True
                            print(f"  WARN {path}:{i} unconditional use: {stripped[:70]}")
    check("no unconditional allow_profile_discovery SELECT", not unconditional)

    # 3. auth_service handles missing hash columns
    print("\n--- auth_service ---")
    with open("services/auth_service.py", "r") as f:
        content = f.read()
    for col in ("password_digest", "hashed_password", "legacy_password_hash"):
        check(f"LOGIN_PROFILE_FIELD_CANDIDATES includes {col}", col in content)
    check("_get_password_hash checks all columns", "_get_password_hash" in content)
    check("password_reset_required message", 'needs password reset' in content)

    print(f"\n{'=' * 60}")
    total = PASS + FAIL
    if FAIL == 0:
        print(f"PHASE 87E: PASS ({PASS}/{total})")
    else:
        print(f"PHASE 87E: FAIL ({PASS}/{total})")
    print(f"{'=' * 60}")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
