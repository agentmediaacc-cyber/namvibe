# Dating Test Matrix

## Offline contracts
- `scripts/test_dating_route_contract.py`
- `scripts/test_dating_profile_privacy_contract.py`
- `scripts/test_dating_discovery_contract.py`
- `scripts/test_dating_match_contract.py`
- `scripts/test_dating_block_contract.py`
- `scripts/test_dating_notification_contract.py`
- `scripts/test_dating_message_authorization_contract.py`
- `scripts/test_dating_compatibility_contract.py`
- `scripts/test_dating_media_contract.py`
- `scripts/test_connecting_you_authorization_contract.py`

## Live integration
- `scripts/test_dating_integration.py`

## Browser
- `scripts/test_release_browser_smoke.py`
- `scripts/test_dating_browser_smoke.py`

## Current status
- Offline contracts are deterministic.
- Live integration exercises temporary real rows and cleans them up.
- Live unmatch and report flows are covered by `scripts/test_dating_integration.py`.
- Dating browser smoke passed 3/3 after rate-limit filtering and slower route cadence.

## Route timings
- `/dating/` cold ~0.005s, warm median ~0.0045s
- `/dating/discover` cold ~0.003s, warm median ~0.0034s
- `/dating/matches` cold ~0.003s, warm median ~0.0030s
- `/dating/preferences` cold ~0.003s, warm median ~0.0029s
- `/dating/connecting-you/` cold ~6.9s, warm median ~6.8s
