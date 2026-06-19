"""Phase 87 — Real Data Audit Test (static checks)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from services.production_content_guard import is_fake_content
    HAS_GUARD = True
except ImportError:
    HAS_GUARD = False

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

def run():
    global PASS, FAIL
    print("Phase 87: Real Data Audit")

    check("production_content_guard module loads", HAS_GUARD)

    if HAS_GUARD:
        check("is_fake_content exists", callable(is_fake_content))

        # Real profiles
        real = {"id": "real-id", "username": "realuser"}
        check("real user not fake", not is_fake_content(real))

        # Fake markers
        fake_username = {"username": "phase8"}
        check("phase8 username is fake", is_fake_content(fake_username))

        fake_seed = {"username": "seed_user"}
        check("seed username is fake", is_fake_content(fake_seed))

        fake_dummy = {"username": "dummy_test"}
        check("dummy username is fake", is_fake_content(fake_dummy))

        fake_lorem = {"body": "lorem ipsum dolor sit amet"}
        check("lorem body is fake", is_fake_content(fake_lorem))

        fake_placeholder = {"username": "placeholder"}
        check("placeholder is fake", is_fake_content(fake_placeholder))

        fake_test_reel = {"caption": "test reel content"}
        check("test reel caption is fake", is_fake_content(fake_test_reel))

        fake_sample = {"username": "sample_user"}
        check("sample username is fake", is_fake_content(fake_sample))

        # Safe users
        safe_users = {"username": "moon", "id": "real-id"}
        check("moon not fake", not is_fake_content(safe_users))

        safe_namvibe = {"username": "namvibe", "id": "real-id"}
        check("namvibe not fake", not is_fake_content(safe_namvibe))

        safe_final = {"username": "final", "id": "real-id"}
        check("final not fake", not is_fake_content(safe_final))

    print(f"\nPhase 87 Real Data Audit: {PASS} passed, {FAIL} failed")
    return FAIL == 0

if __name__ == "__main__":
    success = run()
    sys.exit(0 if success else 1)
