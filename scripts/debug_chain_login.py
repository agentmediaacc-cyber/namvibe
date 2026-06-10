"""
Debug Chain Login — sends POST to the real running app.
Tests browser-equivalent field names.
"""
import sys
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:5000/auth/login"
PASSWORD = "Adimintest"

TESTS = [
    ("login_id", "chain_star", "Adimintest"),
    ("login_id", "chain_star@chain.local", "Adimintest"),
    ("username", "chain_star", "Adimintest"),
    ("email", "chain_star@chain.local", "Adimintest"),
    ("identifier", "chain_star", "Adimintest"),
    ("login", "chain_star", "Adimintest"),
    ("login_id", "chain_star", "wrong_password_123"),
]

PASS = 0
FAIL = 0

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(NoRedirectHandler)

for field_name, field_value, pw in TESTS:
    data = urllib.parse.urlencode({
        field_name: field_value,
        "password": pw,
    }).encode()
    label = f"{field_name}={field_value} pw={'correct' if pw == PASSWORD else 'wrong'}"
    try:
        req = urllib.request.Request(BASE, data=data, method="POST")
        resp = opener.open(req, timeout=10)
        status = resp.status
        location = "(none)"
        body = resp.read().decode("utf-8", errors="replace")[:200]
    except urllib.request.HTTPError as e:
        status = e.code
        location = e.headers.get("Location", "(none)")
        body = e.read().decode("utf-8", errors="replace")[:200]
    except Exception as e:
        print(f"[{label}] EXCEPTION: {e}")
        FAIL += 1
        continue

    if status == 302 and location.startswith("/"):
        print(f"[{label}] status={status} location={location} -> LOGIN SUCCESS")
        PASS += 1
    elif status == 429:
        print(f"[{label}] status={status} -> RATE LIMITED (wait and retry)")
        FAIL += 1
    elif "Invalid password" in body:
        print(f"[{label}] status={status} -> INVALID PASSWORD (expected for wrong pw)")
        if pw != PASSWORD:
            PASS += 1
        else:
            FAIL += 1
    elif "Account not found" in body:
        print(f"[{label}] status={status} -> ACCOUNT NOT FOUND")
        FAIL += 1
    else:
        print(f"[{label}] status={status} location={location} -> UNKNOWN")
        print(f"  body: {body}")
        FAIL += 1

print()
print(f"Results: {PASS}/{PASS + FAIL} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)
