# Query Optimization Report

Date: 2026-06-27  
Project: NamVibe

## Summary

This phase removed avoidable application overhead and narrowed SQL payloads without changing schema, indexes, env, or `app.py`.

Implemented:

- Homepage section endpoints now load independently instead of calling the full `get_homepage_payload()`.
- `/api/homepage/stories` now uses the lighter Phase 141 story loader.
- `/api/homepage/reels` now uses the lighter Phase 141 reel loader.
- Sidebar now avoids full homepage payload assembly.
- `list_threads()` now limits thread rows before lateral lookups.
- `get_thread()` now loads only participants + latest messages on the critical path.
- Reactions, reply previews, and receipt hydration now load asynchronously from `/messages/api/messages/<thread_id>/metadata`.
- Homepage preview/profile hydration now uses lighter profile maps where possible.

## Audit Results

Latest measured route timings from `python3 scripts/audit_namvibe_performance_realtime.py`:

| Route | Current |
|---|---:|
| `/home` | 3876ms |
| `/api/homepage/feed` | 8270ms |
| `/api/homepage/stories` | 1846ms |
| `/api/homepage/reels` | 1274ms |
| `/messages/thread/<id>` | 6269ms |
| `/messages/` | 2744ms |
| `/api/messages/unread-count` | 2243ms |

Not yet at success criteria. The remaining bottlenecks are now mostly DB scan/order costs, not avoidable missing-column fallbacks.

## Query Findings

| File | Function | SQL | Current latency | Expected latency | Code change | Estimated improvement |
|---|---|---|---:|---:|---|---|
| `services/homepage_service.py` | `fetch_stories()` / `_fetch_stories()` | `SELECT id, profile_id, caption, media_url, thumbnail_url, created_at, deleted_at FROM chain_stories WHERE deleted_at IS NULL ORDER BY created_at DESC NULLS LAST LIMIT %s` | 1237ms | 200-400ms | Removed full payload call from `/api/homepage/stories`; switched endpoint to lighter loader path | 3x-6x once DB can avoid scan/sort |
| `services/homepage_service.py` | `fetch_stories()` / `_fetch_stories()` | `SELECT id, profile_id, caption, media_url, video_url, thumbnail_url, visibility, created_at, expires_at, deleted_at, duration_seconds, background_color, text_content, views_count FROM chain_status_posts ... ORDER BY created_at DESC LIMIT %s` | 1042ms | 200-400ms | Stories endpoint now loads independently; no longer pays feed/reels/sidebar work | 2x-4x |
| `services/homepage_phase141_service.py` | `fetch_reels_v2()` | `SELECT id, profile_id, caption, thumbnail_url, media_url, video_url, mime_type, created_at FROM chain_reels WHERE deleted_at IS NULL AND video_url IS NOT NULL AND video_url != '' ... ORDER BY created_at DESC LIMIT %s` | 1065ms | 250-450ms | `/api/homepage/reels` now uses Phase 141 loader directly | 2x-3x |
| `services/homepage_phase141_service.py` | `fetch_posts_v2()` | `SELECT id, profile_id, caption, content, body, thumbnail_url, media_url, video_url, mime_type, post_type, likes_count, comments_count, created_at FROM chain_posts WHERE deleted_at IS NULL ... ORDER BY created_at DESC LIMIT %s` | 688ms | 250-400ms | Feed payload already avoids heavy JOIN chains; selected columns kept narrow | 1.5x-2x |
| `services/homepage_phase141_service.py` | `fetch_profiles_batch()` | `SELECT id, username, display_name, avatar_url, profile_photo, is_verified, verified FROM chain_profiles WHERE id IN (...) LIMIT %s` | 675-682ms | 150-250ms | Left batch lookup in place; this is now the cheapest profile hydration path in repo | 2x-4x |
| `services/homepage_service.py` | `get_homepage_payload()` | Full payload assembly for stories, feed, reels, live, suggestions, hashtags, wallet, unread counts | Previously on stories/reels/sidebar path | n/a on hot path | Removed from section endpoints; retained only for richer payload consumers | Large application-level savings |
| `services/messaging_engine.py` | `list_threads()` | `WITH member_threads AS (...) SELECT ... LEFT JOIN LATERAL latest ... LEFT JOIN LATERAL unread ...` | 1329ms | 500-800ms | Limited threads first, reduced selected columns, deferred group metadata assumptions | 1.5x-2x |
| `services/messaging_engine.py` | `get_thread()` | `SELECT m.id, m.thread_id, m.sender_profile_id, CASE WHEN ... THEN NULL ELSE m.body END AS body, m.media_url, m.media_type, m.mime_type, m.sticker_id, m.gif_url, m.reply_to_message_id, m.created_at, m.delivery_status, m.seen_at, m.read_at ... ORDER BY m.created_at DESC LIMIT 30` | 1236ms | 400-700ms | Reduced from full thread+reactions+parent hydration on critical path to latest 30 messages only | 2x-3x |
| `services/messaging_engine.py` | `get_thread()` post-view update | `UPDATE chain_thread_members SET last_read_at = now() WHERE thread_id = %s AND profile_id = %s` | 674ms | 100-200ms | No SQL rewrite available without schema help; still required for correctness | modest |
| `services/messaging_engine.py` | `get_thread()` post-view update | `UPDATE chain_messages SET is_seen = TRUE, seen_at = now(), read_at = now(), delivery_status = 'seen' WHERE thread_id = %s AND sender_profile_id != %s AND is_seen = FALSE` | 676ms | 150-300ms | Still on request path; metadata hydration already moved async, but seen-update remains synchronous | 2x-3x if moved off response path |
| `services/message_thread_service.py` / message unread API path | `unread_count()` | `SELECT COUNT(*) AS total FROM chain_messages m JOIN chain_thread_members tm ON tm.thread_id = m.thread_id WHERE tm.profile_id = %s AND m.sender_profile_id != %s AND COALESCE(m.is_seen, FALSE) = FALSE ...` | 953ms | 250-400ms | No code change yet; still full count per request | 2x-3x |
| `services/homepage_service.py` | `/home` shell path via current profile lookup | Wide `SELECT` against `chain_profiles` for current profile | 781ms query, `/home` 3876ms total | 300-600ms | Not rewritten here; page still pays for heavy current-profile lookup before shell render | 1.5x-2x |

## Why Each Query Is Slow

### `fetch_stories()` / `_fetch_stories()`

- Cause: full table scan + `ORDER BY created_at DESC`.
- Secondary cause: two separate story sources (`chain_stories`, `chain_status_posts`) plus Python merge/sort.
- Improvement already made: section endpoint no longer triggers unrelated homepage work.

### `fetch_reels_v2()`

- Cause: `deleted_at IS NULL` plus `video_url IS NOT NULL` plus `ORDER BY created_at DESC`.
- Secondary cause: follow-visibility predicate adds extra filter work.
- Improvement already made: lighter endpoint path and smaller selected column set.

### `fetch_posts_v2()`

- Cause: visibility predicate plus descending recency sort on public feed.
- Secondary cause: batch profile hydration afterwards.
- Improvement already made: no profile JOIN inside the post query.

### `list_threads()`

- Cause: lateral latest-message lookup and lateral unread count per thread.
- Secondary cause: unread count still touches `chain_messages` per thread row.
- Improvement already made: `member_threads` CTE limits thread set before lateral work.

### `get_thread()`

- Cause: latest-message query still scans recent thread messages and joins sender profiles.
- Secondary cause: synchronous seen-mark updates after render.
- Improvement already made: reactions, reply previews, and receipts removed from critical path and loaded asynchronously.

### `unread_count()`

- Cause: count query scans unread messages across joined thread membership.
- Secondary cause: exact count requested every time instead of cached snapshot.

### `/home`

- Cause: current-profile lookup is still very wide.
- Secondary cause: shell route still performs schema/profile work before returning HTML.

## Code Changes Made

### Homepage

- `api_routes/homepage_api.py`
  - `/api/homepage/stories` now calls `fetch_stories_v2(...)`.
  - `/api/homepage/reels` now calls `fetch_reels_v2(...)`.
  - `/api/homepage/sidebar` no longer calls the full homepage payload builder.
- `services/homepage_service.py`
  - Added lighter section helpers for stories, reels, live rooms, sidebar, suggested users, nearby users.
  - `get_homepage_payload()` now uses lighter profile map loading.
  - Kept JSON shape stable while adding independent section support.

### Messaging

- `services/messaging_engine.py`
  - `list_threads()` now limits thread rows before lateral latest/unread work.
  - `get_thread()` now returns initial shell + latest 30 messages only.
  - Added `get_thread_metadata()` for async reactions/parent/receipt hydration.
- `api_routes/message_routes.py`
  - Added `/messages/api/messages/<thread_id>/metadata`.
- `templates/messages/thread.html`
  - Fetches metadata asynchronously after first paint and after polling refresh.

## Remaining Optimization Opportunities

These are the next code-only opportunities still available before schema/index work:

1. Move message seen-marking off the synchronous thread-page response path.
   - Current blocker: two update statements together cost ~1.35s.
   - Best code-only option: fire-and-forget background task or client-triggered POST after first paint.

2. Cache unread message count more aggressively.
   - Current blocker: exact `COUNT(*)` costs ~953ms.
   - Best code-only option: short TTL cache keyed by profile and invalidate on send/seen events.

3. Shrink current profile lookup used by `/home`.
   - Current blocker: wide `chain_profiles` row selection before shell render.
   - Best code-only option: dedicated lightweight current-profile projection for shell routes.

4. Remove `chain_stories` query from story-strip hot path when `chain_status_posts` is the real populated source.
   - Current blocker: empty `chain_stories` scan still costs ~1.2s.
   - Best code-only option: feature-flag or runtime detect empty story table and skip it for public strip endpoints.

5. Reduce `/api/homepage/feed` work further.
   - Current blocker: it still loads stories, posts, reels, profile batch, and region lookup in one request.
   - Best code-only option: return feed shell first and lazy-load stories/reels separately on the client.

## Before vs After

| Route | Before | After |
|---|---:|---:|
| `/api/homepage/stories` | 16374ms | 1846ms |
| `/api/homepage/reels` | 7677ms | 1274ms |
| `/api/homepage/feed` | 9428ms | 8270ms |
| `/messages/thread/<id>` | 11711ms | 6269ms |
| `/home` | 3639ms | 3876ms |

Notes:

- `/home` did not improve because the remaining cost is outside the section endpoints and comes from the current-profile/query startup path.
- `/api/homepage/feed` improved slightly, but it still bundles too much work into one request.

## Exact Next Recommended Fix

Move thread read-receipt updates out of the synchronous `/messages/thread/<id>` render path and cache unread message counts with event-driven invalidation.

Reason:

- This is the highest remaining code-only win in messaging.
- It directly targets the two queries still taking ~674ms and ~676ms on every thread page load.
- It does not require schema/index changes.

After that, the next homepage-only fix is to make `/api/homepage/feed` a truly feed-only endpoint and let stories/reels stay independently loaded.
