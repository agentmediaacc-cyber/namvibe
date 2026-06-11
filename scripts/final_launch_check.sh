#!/usr/bin/env bash
set -u

BASE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$BASE_DIR" || exit 1

if [ -d "venv" ]; then
  # shellcheck disable=SC1091
  . "venv/bin/activate"
elif [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  . ".venv/bin/activate"
fi

PASS=0
FAIL=0
declare -a ROWS=()

run_check() {
  local name="$1"
  shift
  echo ""
  echo "== $name =="
  "$@"
  local status=$?
  if [ "$status" -eq 0 ]; then
    ROWS+=("PASS|$name")
    PASS=$((PASS + 1))
  else
    ROWS+=("FAIL|$name")
    FAIL=$((FAIL + 1))
  fi
  return 0
}

echo "CHAIN final production launch verification"
echo "Base: $BASE_DIR"

run_check "compileall" python3 -m compileall .
run_check "security remediation" python3 scripts/test_security_remediation.py
run_check "phase69 real communication" python3 scripts/test_phase69_real_communication.py
run_check "phase73 homepage real data" python3 scripts/test_phase73_homepage_real_data.py
run_check "phase74 full upgrade speed" python3 scripts/test_phase74_full_upgrade_speed.py
run_check "phase75 real user journey" python3 scripts/test_phase75_real_user_journey.py
run_check "phase76 load and scale" python3 scripts/test_phase76_load_and_scale.py
run_check "final launch check" python3 scripts/final_launch_check.py

echo ""
echo "FINAL PASS/FAIL TABLE"
printf "%-8s %s\n" "STATUS" "CHECK"
printf "%-8s %s\n" "------" "-----"
for row in "${ROWS[@]}"; do
  status="${row%%|*}"
  name="${row#*|}"
  printf "%-8s %s\n" "$status" "$name"
done

echo ""
echo "PASS: $PASS"
echo "FAIL: $FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "FINAL DECISION: GO"
  exit 0
fi

echo "FINAL DECISION: NO-GO"
exit 1
