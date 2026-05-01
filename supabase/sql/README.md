# Namvibe Supabase SQL Review Pack

These SQL files are reviewed foundation scripts for Supabase/Postgres hardening.

Important:
- Review every table and column name against the live Supabase schema before execution.
- Do not run these files blindly in production.
- Do not use these files to drop data or disable existing protections.
- Service-role operations must remain server-side only.
- Storage policies assume user-scoped object paths such as `avatars/<auth.uid()>/...` and must be adjusted if your bucket layout differs.
- Add or keep matching indexes before enabling high-traffic RLS policies in production.

Suggested order:
1. `001_rls_enable_public_tables.sql`
2. `002_social_policies.sql`
3. `003_storage_policies.sql`
4. `004_indexes_for_social_performance.sql`

Validation checklist before execution:
- Confirm `auth.uid()` maps to the same user identity stored in each table.
- Confirm audience/status column names match the real schema.
- Confirm friendship/follow relationships are represented by the expected table names and accepted status values.
- Confirm storage bucket names and folder structure.
- Run on staging first.
