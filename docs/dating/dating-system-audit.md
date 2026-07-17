# Dating System Audit

## Canonical routes
- `/dating/` landing
- `/dating/discover` discovery
- `/dating/profile/<profile_id>` public profile shell
- `/dating/matches` match list
- `/dating/preferences` preferences
- `/dating/safety` safety center
- `/dating/api/*` JSON endpoints
- `/connecting-you/*` program flows

## Canonical services
- `services/dating_service.py`
- `services/dating_compatibility_service.py`
- `services/connecting_you_service.py`
- `services/notification_service.py`
- `services/messaging_engine.py`
- `services/blocking_service.py`

## Schema
- `chain_dating_profiles`
- `chain_dating_preferences`
- `chain_dating_likes`
- `chain_dating_matches`
- `chain_dating_blocks`
- `chain_dating_reports`
- `chain_profiles`
- `chain_thread_members`
- `chain_message_threads`
- `chain_notifications` / `chain_notification_events`

## Findings
- Discovery now uses real eligible users with block and pause filtering.
- Matching is mutual and idempotent.
- Messaging is gated on active matches and blocked status.
- Notifications are emitted on real match creation.
- Dating photos reuse the canonical media pipeline.
- Connecting You remains a separate program and requires authorization checks.
