# NamVibe AI Phase 1A

Phase 1A adds a production-safe AI foundation with deterministic recommendations and interaction tracking. External AI calls remain disabled by default.

## Architecture

- `services/ai/config.py` reads optional AI environment variables with safe defaults.
- `services/ai/provider_*` provides an import-safe provider abstraction with a disabled provider implementation.
- `services/ai/privacy_guard.py` strips prohibited sensitive fields before any external payload could be considered.
- `services/ai/feature_flags.py` reads `chain_ai_feature_flags` with short-lived caching and deterministic rollout.
- `services/ai/interaction_service.py` records AI interaction analytics without breaking product actions on failure.
- `services/ai/user_profile_service.py` builds AI profile context from real profile fields and recent interactions only.
- `services/ai/recommendation_service.py` ranks profiles, posts, and reels deterministically without any external LLM.
- `api_routes/ai_routes.py` exposes authenticated `/api/ai/*` endpoints and preserves the existing `/ai/` page route.

## Schema

Migration file: `sql/phase_ai_platform.sql`

Tables:
- `chain_ai_user_profiles`
- `chain_ai_interactions`
- `chain_ai_recommendation_events`
- `chain_ai_provider_usage`
- `chain_ai_feature_flags`

Indexes are included for lookup by profile, time, request, and provider usage dimensions.

Foreign keys were intentionally not added because NamVibe environments already vary in profile schema/runtime shape, and Phase 1A must deploy safely without cross-environment table coupling failures.

## Feature Flags

Flags live in `chain_ai_feature_flags`.

Default behavior:
- `ai_interaction_tracking`: enabled
- `ai_recommendations`: disabled
- all external/provider features: disabled

Rollouts are deterministic per `feature_key + profile_id`.

## Privacy Rules

- External AI is disabled by default.
- No API keys are exposed to templates or frontend JavaScript.
- Recursive sanitization removes prohibited keys such as passwords, tokens, email, phone, wallet keys, and exact coordinates.
- Text, lists, and dictionaries are size-capped before storage or provider payload construction.
- Unsafe external payloads are rejected.

## Recommendation Signals

Profile recommendations:
- shared interests
- same region
- same town
- profile completeness
- verified status

Content recommendations:
- freshness
- engagement
- creator locality
- shared interests
- verified creator signal
- deterministic exploration bonus

Negative filtering:
- blocked creator/profile exclusion
- hidden and reported targets from prior tracked interactions
- self exclusion
- existing friends excluded from new-connection profile recommendations

## Environment Configuration

Documented in `.env.example`:

```env
NAMVIBE_AI_ENABLED=false
NAMVIBE_AI_PROVIDER=disabled
NAMVIBE_AI_MODEL=
NAMVIBE_AI_API_KEY=
NAMVIBE_AI_BASE_URL=
NAMVIBE_AI_TIMEOUT_SECONDS=12
NAMVIBE_AI_MAX_RETRIES=1
NAMVIBE_AI_RECOMMENDATIONS_ENABLED=false
NAMVIBE_AI_INTERACTION_TRACKING_ENABLED=true
NAMVIBE_AI_EXTERNAL_CALLS_ENABLED=false
NAMVIBE_AI_LOG_PROVIDER_USAGE=true
NAMVIBE_AI_CACHE_TTL_SECONDS=120
NAMVIBE_AI_RECOMMENDATION_VERSION=v1
```

## Local Setup

1. Apply the SQL migration.
2. Keep AI defaults disabled unless you are explicitly testing rollout behavior.
3. Run the test scripts below.

## Migration Command

Use your normal NamVibe Neon/Postgres migration workflow to apply:

`sql/phase_ai_platform.sql`

## Testing Commands

```bash
python -m compileall services/ai api_routes/ai_routes.py
python scripts/test_phase_ai_foundation.py
python scripts/test_phase_ai_privacy.py
python scripts/test_phase_ai_recommendations.py
python scripts/test_phase_ai_routes.py
```

## Safe Rollout Plan

1. Apply migration with all recommendation flags disabled.
2. Leave interaction tracking on for data collection.
3. Verify `GET /api/ai/status` in staging/production.
4. Enable `ai_recommendations` for internal profiles only by rollout percentage or selective profile sampling.
5. Watch database latency, route error rate, and cache behavior before wider rollout.

## Rollback Plan

1. Set `ai_recommendations` to disabled in `chain_ai_feature_flags`.
2. Set `NAMVIBE_AI_ENABLED=false` if broader AI behavior must be frozen.
3. Stop loading any optional frontend tracking hook integrations if added later.
4. Leave data tables in place; Phase 1A schema is additive and can remain dormant safely.

## Future Provider Implementation

- Add a provider module under `services/ai/`.
- Keep provider selection explicit in `provider_factory.py`.
- Pass only privacy-guarded payloads.
- Log usage through `chain_ai_provider_usage`.
- Keep external calls behind `NAMVIBE_AI_EXTERNAL_CALLS_ENABLED=true` and the matching feature flag.

## Known Limitations

- Phase 1A recommendations are deterministic heuristics, not model-generated rankings.
- Existing branch AI assistant routes are not expanded here into external provider execution.
- Optional schema differences across environments can reduce signal richness, but endpoints degrade to safe empty responses.
