# CHAIN Phase 36 — Load Test Report

Generated: 2026-06-06 14:06:00 UTC

## Summary

- Passed: 7/7
- Failed: 0/7


### 50 Users
| Route | Requests | Avg (ms) | Max (ms) | OK | Fail |
|---|---|---|---|---|---|
| `/` | 50 | 157.7 | 7461.3 | 50 | 0 |
| `/messages/` | 50 | 9.6 | 26.6 | 50 | 0 |
| `/calls/recent` | 50 | 104.0 | 4900.5 | 50 | 0 |
| `/live/` | 50 | 28.3 | 1077.0 | 50 | 0 |
| `/profile/` | 50 | 32.4 | 1259.5 | 50 | 0 |
| `/notifications/` | 50 | 11.4 | 277.5 | 50 | 0 |

## Verdict

- [x] All load tests passed

*Note: Tested via Flask test client sequentially. Real production load testing requires Locust or k6.*
