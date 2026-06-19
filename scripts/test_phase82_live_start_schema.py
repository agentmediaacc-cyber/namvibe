"""Phase 82: live start uses schema-compatible dynamic insert."""
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
    print("Phase 82: Live Start Schema")
    feature = open("services/live_feature_service.py").read()
    service = open("services/live_service.py").read()
    route = open("api_routes/live_routes.py").read()

    check("feature service inspects live room columns", "get_cached_table_columns(\"chain_live_rooms\")" in feature)
    check("feature service dynamically builds insert", "insert_columns" in feature and "INSERT INTO chain_live_rooms" in feature)
    check("feature service avoids hardcoded host_profile_id insert", "profile_id, host_profile_id" not in feature)
    check("feature service returns missing owner error", "live_rooms_missing_owner_column" in feature)
    check("form live service filters payload to columns", "dynamic_payload" in service and "live_columns" in service)
    check("route uses start_live API", "phase29_live.start_live" in route)

    print(f"\nPhase 82 Live Start Schema: {PASS} passed, {FAIL} failed")
    return FAIL == 0


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
