# CHAIN Phase 35 — Load Smoke Test Results
Generated: 2026-06-06 13:53:56 UTC

## Summary

- Total requests: 80
- Passed: 12/12
- Failed: 0/12

## Per-Route Results

| Route | Requests | Avg (ms) | Max (ms) | Success | Failures |
|-------|----------|----------|----------|---------|----------|
| `/` | 20 | 409.6 | 8143.3 | 20 | 0 |
| `/messages/` | 20 | 1.2 | 1.5 | 20 | 0 |
| `/calls/recent` | 10 | 1.7 | 3.1 | 10 | 0 |
| `/live/` | 10 | 2.3 | 9.0 | 10 | 0 |
| `/notifications/` | 10 | 1.3 | 1.5 | 10 | 0 |
| `/profile/` | 10 | 1.4 | 1.8 | 10 | 0 |

## Verdict

- [x] All requests passed
- [ ] Performance degradation detected

*This is a local smoke test. Real production load testing requires a dedicated tool like Locust or k6.*
