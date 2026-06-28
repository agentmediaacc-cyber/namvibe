# Thread Name Column Fix

## Problem

Runtime SQL error on `/messages/` and related routes:

```
column t.thread_name does not exist
HINT: Perhaps you meant t.thread_type.
```

The `chain_message_threads` table's core schema (`chain_neon_core_schema.sql`) does not include a `thread_name` column. While later migrations (`social_rebuild_upgrade.sql`, `phase29_communication_live_creator.sql`) attempt to add it, those migrations may not have run in the deployed environment.

Additionally, `t.thread_avatar_url` had the same issue — not present in the core schema.

## Files Changed

### `api_routes/inbox_routes.py`
- Added `_thread_name_expr(table_alias)` helper that uses `get_cached_table_columns("chain_message_threads")` to detect whether `thread_name`, `title`, `name`, or `display_name` exists at runtime.
- Both SQL queries (inbox + sent tabs) now inject the detected column expression via f-string instead of hardcoding `t.thread_name`.

### `services/messaging_engine.py`
- Added `_thread_name_expr(table_alias)` and `_thread_avatar_expr(table_alias)` helpers using the same runtime column detection.
- `list_threads()` CTE: `t.thread_name` → dynamic expression aliased as `thread_name`; `t.thread_avatar_url` → dynamic expression aliased as `thread_avatar_url`.
- `search_messages()`: `t.thread_name` → dynamic expression aliased as `thread_name`.
- Python dict access at line 118 (`thread.get('thread_name')`) unchanged — SQL alias remains `thread_name`.

## Detection Order

For `thread_name`: checks columns in order `thread_name` → `title` → `name` → `display_name`. Falls back to the literal `'Conversation'`.

For `thread_avatar_url`: checks `thread_avatar_url` → `avatar_url`. Falls back to `NULL`.

## Verification

```bash
python3 -m py_compile app.py
python3 -m compileall api_routes services templates
python3 scripts/verify_production_routes.py
python3 scripts/benchmark_production_routes.py
```

All four passed.
