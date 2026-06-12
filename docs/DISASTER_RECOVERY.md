# NAMVIBE DISASTER RECOVERY PLAN

## 1. Database Backups
- **Primary DB (Neon/PostgreSQL):**
  - Continuous WAL archiving enabled.
  - Daily snapshots taken automatically via Neon Console.
  - Manual logical dump script: `scripts/backup_db.sh` (runs daily at 02:00 UTC).
- **In-Memory Store (Redis):**
  - RDB snapshots every 15 minutes.
  - AOF enabled for per-command persistence.

## 2. Media Storage Backups
- **Object Storage (Supabase/R2/S3):**
  - Versioning enabled on all critical buckets (avatars, verification).
  - Cross-region replication enabled for `chain-posts` and `chain-reels`.
  - Manual sync script: `scripts/sync_media_backup.sh` to move data to secondary provider.

## 3. Recovery Procedures
### Database Point-in-Time Recovery (PITR)
1. Log into Neon Console.
2. Select "Branches" -> "Create Branch from Point in Time".
3. Verify data in new branch.
4. Update connection string in `.env` to point to the new branch.

### Media Recovery
1. Identify missing files from `chain_media_uploads` metadata table.
2. Restore from backup provider using `scripts/restore_media.py`.

## 4. Emergency Contacts
- **DevOps/Infrastructure:** infrastructure@chain.social
- **Security Lead:** security@chain.social
