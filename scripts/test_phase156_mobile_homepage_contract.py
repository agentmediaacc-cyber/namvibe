"""
Phase 156 — Mobile Homepage Contract Test

Must verify:
- Hamburger button exists in template
- Drawer exists with all required nav items
- Bottom nav has correct items
- Hero section has CSS class to hide on mobile
- Input elements have 16px font-size on mobile
- No old sidebar links visible on mobile

Usage:
    python3 scripts/test_phase156_mobile_homepage_contract.py
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def check_file(filepath):
    results = {"pass": 0, "fail": 0, "details": []}
    with open(filepath) as f:
        content = f.read()

    # 1. Hamburger button exists
    if 'nvpro-hamburger' in content:
        results["details"].append(("Hamburger button exists", True))
        results["pass"] += 1
    else:
        results["details"].append(("Hamburger button missing", False))
        results["fail"] += 1

    # 2. Drawer exists
    if 'nvpro-drawer' in content:
        results["details"].append(("Drawer element exists", True))
        results["pass"] += 1
    else:
        results["details"].append(("Drawer element missing", False))
        results["fail"] += 1

    # 3. Drawer nav items - find the HTML drawer section (after style block, before body)
    drawer_start = content.find('class="nvpro-drawer-items"')
    if drawer_start > 0:
        drawer_html = content[drawer_start:drawer_start + 5000]
    else:
        drawer_html = ""
    drawer_spans = re.findall(r'>([^<]+)</span>', drawer_html)
    
    required_items = ["Home", "Discover", "Live", "Reels", "Stories", "Inbox", "Contacts", "Calls", "Dating", "Wallet", "Profile", "Settings"]
    missing = [i for i in required_items if i not in drawer_spans]
    if not missing:
        results["details"].append(("Drawer has all required nav items", True))
        results["pass"] += 1
    else:
        results["details"].append((f"Drawer missing items: {missing}", False))
        results["fail"] += 1

    # 4. "Sign Out" link exists in drawer
    if 'nvpro-drawer-signout' in drawer_html:
        results["details"].append(("Sign Out in drawer", True))
        results["pass"] += 1
    else:
        results["details"].append(("Sign Out missing from drawer", False))
        results["fail"] += 1

    # 5. Bottom nav exists
    if 'nvpro-bottom-nav' in content:
        results["details"].append(("Bottom nav exists", True))
        results["pass"] += 1
    else:
        results["details"].append(("Bottom nav missing", False))
        results["fail"] += 1

    # 6. CSS hides hero on mobile
    if '@media (max-width:768px)' in content and '.nvpro-home-hero { display:none' in content:
        results["details"].append(("Hero hidden on mobile via CSS", True))
        results["pass"] += 1
    else:
        results["details"].append(("Hero not hidden on mobile", False))
        results["fail"] += 1

    # 7. CSS hides left rail on mobile
    if '@media (max-width:768px)' in content and '.nvpro-left-rail { display:none' in content:
        results["details"].append(("Left rail hidden on mobile via CSS", True))
        results["pass"] += 1
    else:
        results["details"].append(("Left rail not hidden on mobile", False))
        results["fail"] += 1

    # 8. Input font-size 16px on mobile
    if 'font-size:16px !important' in content:
        results["details"].append(("Inputs have 16px font-size on mobile", True))
        results["pass"] += 1
    else:
        results["details"].append(("Inputs missing 16px font-size on mobile", False))
        results["fail"] += 1

    return results

def main():
    print("=" * 60)
    print("Phase 156 — Mobile Homepage Contract Test")
    print("=" * 60)

    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates/chain_home.html")
    print(f"\nChecking {template_path}...\n")

    results = check_file(template_path)

    for desc, ok in results["details"]:
        print(f"  {'✅' if ok else '❌'} {desc}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {results['pass']} PASS / {results['fail']} FAIL / {results['pass'] + results['fail']} TOTAL")
    print("=" * 60)
    return 1 if results['fail'] > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
