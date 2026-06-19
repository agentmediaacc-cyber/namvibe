"""Phase 82: homepage has one desktop nav, one mobile nav, one drawer."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        print(f"  OK  {name}")
        PASS += 1
    else:
        print(f"  FAIL {name}")
        FAIL += 1


def run():
    print("Phase 82: Home Nav Static")
    tpl = open("templates/chain_home.html").read()
    check("one desktop left nav", tpl.count('class="nv-left-nav"') == 1)
    check("one mobile topbar", tpl.count('class="nv-mobile-topbar"') == 1)
    check("one bottom mobile nav", tpl.count('class="nv-bottom-nav"') == 1)
    check("one mobile drawer", tpl.count('class="nv-mobile-drawer"') == 1)
    check("one drawer backdrop", tpl.count('class="nv-drawer-backdrop"') == 1)
    check("base nav disabled on homepage", "{% block top_header %}{% endblock %}" in tpl and "{% block mobile_nav %}{% endblock %}" in tpl)
    check("no old chain drawer id included", "chain-home-drawer" not in tpl)
    check("no duplicate sign out labels", tpl.count("Sign Out") <= 2)

    print(f"\nPhase 82 Home Nav: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
