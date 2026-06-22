# NamVibe Rollback Plan

## When to Rollback

Trigger a rollback when any of the following occur:

- **Auth broken** — users cannot register or log in
- **Data loss** — messages, profiles, or wallet records corrupted
- **Wallet errors** — incorrect balances, duplicate payouts, failed transactions
- **Security breach** — unauthorized access to user data or admin functions
- **Critical API down** — core endpoints return 500 for >5 min
- **DB connection lost** — Neon pool exhausted or circuit breaker open

---

## Rollback Procedures

### 1. Git Rollback

```bash
# Identify the last known-good commit
git log --oneline -10

# Reset to the previous stable commit
git reset --hard <last-good-commit-hash>

# Force push to revert the deployment branch
git push --force-with-lease origin phase113-production
```

> **Warning:** Force-push only if you are the sole contributor on the branch, or have coordinated with the team. Prefer reverting with a new commit (`git revert`) when working in a shared branch.

### 2. Cloud Run Rollback

```bash
# List revisions
gcloud run revisions list --service chain-app --region us-central1

# Rollback to the previous revision
gcloud run services update chain-app --region us-central1 --no-traffic
gcloud run services update-traffic chain-app --region us-central1 --to-revisions=<previous-revision>=100
```

Or use the Cloud Console:
1. Go to Cloud Run → chain-app
2. Click "Managed revisions"
3. Find the last known-good revision
4. Click "..." → "Deploy with this revision"

### 3. Render Rollback

1. Go to Render Dashboard → chain-app
2. Click "Events" tab
3. Find the last successful deploy
4. Click "..." → "Deploy" to redeploy that version

Or via the API:
```bash
curl -X POST https://api.render.com/v1/services/<service-id>/deploys/<deploy-id>/rollback \
  -H "Authorization: Bearer $RENDER_API_KEY"
```

### 4. Environment Variable Rollback

1. Go to Cloud Run → chain-app → "Variables & Secrets"
2. Restore previous values from a backup copy
3. Click "Deploy new revision"

For Render: Dashboard → chain-app → "Environment" tab → restore values → "Save"

### 5. Database Rollback (Point-in-Time Recovery)

```bash
# 1. Create a branch at the point before the incident
#    (via Neon Console → Branches → Create Branch from Point in Time)

# 2. Update DATABASE_URL to point to the restored branch
#    DATABASE_URL=postgresql://...@<restored-branch>.neon.tech/...

# 3. Redeploy the app with the new DATABASE_URL
```

### 6. Disable Wallet Payouts (Emergency)

```bash
# Set this env var and redeploy:
CHAIN_DISABLE_PAYOUTS=1
```

This disables all payout creation and approval endpoints. Existing pending payouts remain in the database but cannot be processed.

### 7. Disable Registration (Emergency)

```bash
# Set this env var and redeploy:
CHAIN_DISABLE_REGISTRATION=1
```

New users will see a "Registration temporarily disabled" message. Existing users can still log in.

### 8. Maintenance Mode

Set the following env vars and redeploy:

```bash
CHAIN_MAINTENANCE_MODE=1
CHAIN_MAINTENANCE_MESSAGE="NamVibe is undergoing maintenance. Please check back shortly."
```

When maintenance mode is active:
- All non-authenticated routes show a maintenance page
- API endpoints return 503 with the maintenance message
- Admins can still access `/admin/*` routes
- Health endpoints (`/healthz`, `/health/db`) remain accessible for monitoring

---

## Post-Rollback Verification

After rolling back, verify:

1. `curl https://<host>/healthz` returns 200
2. `curl https://<host>/health/db` returns `connected: true`
3. Test registration and login with a test account
4. Send a test message
5. Verify wallet balance for a test user
6. Check Sentry (or error logs) for new errors

## Rollback Contacts

- **DevOps:** infrastructure@chain.social
- **Security:** security@chain.social
- **Emergency:** +1 (555) 000-0000
