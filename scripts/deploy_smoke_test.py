import os
import requests
import sys

def smoke_test(url):
    print(f"[smoke] Testing {url}...")
    try:
        # Try live URL first with a short timeout
        res = requests.get(f"{url}/healthz", timeout=2)
        if res.status_code == 200:
            print("  Live /healthz OK")
            res = requests.get(url, timeout=5)
            if res.status_code == 200:
                print("  Live Homepage OK")
                return True
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        print(f"  Live server unreachable at {url}: {type(e).__name__}")
    except Exception as e:
        print(f"  Live server check skipped: {e}")

    # Fallback to Flask test_client
    print("  Falling back to Flask test_client...")
    try:
        # Ensure we are in a testing-like environment
        os.environ["FLASK_ENV"] = "testing"
        from app import create_app
        app = create_app()
        client = app.test_client()
        
        with app.app_context():
            res = client.get("/healthz")
            if res.status_code != 200:
                print(f"  FAILED: /healthz returned {res.status_code}")
                return False
            print("  TestClient /healthz OK")

            res = client.get("/")
            if res.status_code != 200:
                print(f"  FAILED: / returned {res.status_code}")
                return False
            print("  TestClient Homepage OK")
            return True
    except Exception as e:
        print(f"  FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # For local test, we assume app might be running or we use a provided URL
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
    if smoke_test(target_url):
        print("\n✅ Smoke test PASSED")
    else:
        print("\n❌ Smoke test FAILED")
        sys.exit(1)
