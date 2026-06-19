"""Phase 82: /security no longer 404s."""
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
    print("Phase 82: Security Route")
    src = open("api_routes/security_routes.py").read()
    check("security index route exists", '@security_bp.route("/")' in src and '@security_bp.route("")' in src)
    check("security index redirects to privacy", "security.privacy_page" in src and "redirect(" in src)

    from app import app
    app.config.update(TESTING=True, SECRET_KEY="phase82-security")
    with app.test_client() as client:
        response = client.get("/security", follow_redirects=False)
        check("/security does not 404", response.status_code in (200, 302, 401))
        check("/security redirects or auth-gates safely", response.status_code != 404)

    print(f"\nPhase 82 Security Route: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
