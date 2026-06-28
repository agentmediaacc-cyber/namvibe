# PostgreSQL Index Recommendations

> DO NOT apply these automatically. Each index should be reviewed during a maintenance window.

---

## 1. Homepage Content — Stories / Status Posts

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_stories_deleted_created
    ON chain_stories (deleted_at, created_at DESC)
    WHERE deleted_at IS NULL;
```

- Affected: services/homepage_service.py -> _fetch_stories
- Benefit: Biggest lever for 17.4s home latency.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_status_posts_expires_deleted_created
    ON chain_status_posts (expires_at, deleted_at, created_at DESC)
    WHERE deleted_at IS NULL;
```

- Affected: Status post expiry filter in _fetch_stories
- Benefit: Speeds up expires_at > now() visibility pruning.

---

## 2. Reels + Posts + Live Rooms

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_reels_visibility_status_created
    ON chain_reels (visibility, status, processing_status, created_at DESC)
    WHERE deleted_at IS NULL;
```

- Affected: services/reels_service.py, homepage _fetch_reels
- Benefit: Expected 5.4s -> <800ms Reels load.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_posts_visibility_deleted_created
    ON chain_posts (visibility, deleted_at, created_at DESC)
    WHERE deleted_at IS NULL;
```

- Affected: services/feed_engine.py + homepage feed post query
- Benefit: Supports COALESCE(visibility, 'public') = 'public' with index-only scan.

---

## 3. Messaging Queries

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_thread_members_profile_thread
    ON chain_thread_members (profile_id, thread_id);
```

- Affected: services/messaging_engine.py list_threads, unread_count
- Benefit: Transforms thread lookup from ~12.8s to <1s.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_messages_thread_created
    ON chain_messages (thread_id, created_at DESC, deleted_at)
    WHERE deleted_at IS NULL;
```

- Affected: message_thread_service.py latest/older messages
- Benefit: Supports LATERAL sub-query without sequential scan of chain_messages.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_blocks_blocker_blocked
    ON chain_blocks (blocker_profile_id, blocked_profile_id)
    WHERE deleted_at IS NULL;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_blocks_blocked_blocker
    ON chain_blocks (blocked_profile_id, blocker_profile_id)
    WHERE deleted_at IS NULL;
```

- Affected: services/feed_engine.py viewer-exclusion clause
- Benefit: Eliminates scan on block checks for every visible profile.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_mutes_muter_muted
    ON chain_mutes (muter_profile_id, muted_profile_id)
    WHERE deleted_at IS NULL;
```

- Affected: Feed / homepage visibility filtering
- Benefit: Same as above for mute checks.

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chain_live_rooms_status_is_live
    ON chain_live_rooms (status, is_live, deleted_at, created_at DESC)
    WHERE deleted_at IS NULL;
```

- Affected: services/homepage_phase141_service.py fetch_live_rooms_v2
- Benefit: Direct index hit for is_live = TRUE OR status = 'live' predicate.

---

## Summary: Estimated Cumulative Impact

| Route   | Current | With Indexes + Code Changes | Primary Index Driver                          |
|---------|---------|-----------------------------|-----------------------------------------------|
| Home    | 17.4 s  | <2 s                        | idx_chain_stories_deleted_created             |
| Thread  | 12.8 s  | <1 s                        | idx_chain_thread_members_profile_thread       |
| Stories | 7.8 s   | <800 ms                     | idx_chain_stories_deleted_created             |
| Reels   | 5.4 s   | <800 ms                     | idx_chain_reels_visibility_status_created     |