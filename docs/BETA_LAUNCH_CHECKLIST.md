# NamVibe Beta Launch Checklist

## Phase 118-119: Limited Beta Readiness

Use this checklist before and during the limited beta. Items are ordered by criticality.

---

## 1. Environment Variables

- [ ] `SECRET_KEY` — strong random value, ≥32 chars, not the dev default
- [ ] `DATABASE_URL` — Neon PostgreSQL connection string (pooler endpoint)
- [ ] `REDIS_URL` or `REDIS_TLS_URL` — Upstash Redis with rediss:// TLS
- [ ] `SUPABASE_URL` — Supabase project URL
- [ ] `SUPABASE_ANON_KEY` — Supabase anon/public key
- [ ] `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key (keep secret)
- [ ] `FLASK_ENV=production`
- [ ] `ENV=production`
- [ ] `ALLOW_LOCAL_AUTH_FALLBACK=false` (or unset)
- [ ] `SENTRY_DSN` — (recommended) error tracking
- [ ] `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` — (recommended) for video calls
- [ ] `TURN_SERVER_URL`, `TURN_USERNAME`, `TURN_PASSWORD` — (recommended) for WebRTC relay
- [ ] `APP_BASE_URL` — public base URL of the deployment

## 2. Cloud Run / Render Deployment

- [ ] `gcloud run deploy` command tested and succeeds
- [ ] Render Blueprint deploys without errors
- [ ] Dockerfile builds in CI (no missing system deps)
- [ ] Health endpoint `/healthz` returns 200
- [ ] `/health/db` returns connected: true
- [ ] `/health/redis` returns connected: true or fallback active
- [ ] All secrets from Secret Manager or Render Dashboard, never in git

## 3. Auth & Security

- [ ] Registration works with Supabase auth
- [ ] Login works with Supabase auth
- [ ] Local auth fallback is disabled in production
- [ ] CSRF protection enabled on all form routes
- [ ] Debug routes (`/dev/*`) not accessible in production
- [ ] Admin routes require `require_admin` decorator
- [ ] Payout routes require auth and admin approval
- [ ] Rate limiting enabled
- [ ] Upload size limit enforced

## 4. Core Features

- [ ] Profile creation and editing works
- [ ] Follow/unfollow works
- [ ] Friend request / accept / reject works
- [ ] Messaging: send, receive, seen, delivered
- [ ] Calling: WebRTC signaling works
- [ ] Stories: create, view, react, reply
- [ ] Reels: upload, like, comment, share, save
- [ ] Discovery: profiles, trending, live rooms load
- [ ] Notifications: receive and display
- [ ] Wallet: view balance, transactions

## 5. Beta User Management

- [ ] User list maintained (max 20 for initial beta)
- [ ] Each user's profile verified manually
- [ ] Feedback channel established (email, chat, form)
- [ ] Bug report template shared with beta users
- [ ] Test on Android, iPhone, and laptop before inviting others

## 6. Monitoring

- [ ] `/healthz` checked by external uptime monitor
- [ ] Neon pool health reviewed every 15 min initially
- [ ] Redis memory usage monitored
- [ ] Worker queues healthy (no stuck jobs)
- [ ] Error logs reviewed daily

## 7. Wallet / Payouts

- [ ] Wallet payouts manual-approve only during beta
- [ ] Payout request review process documented
- [ ] Platform fee configuration verified
- [ ] No automatic payouts without admin review

## 8. Final Checks Before Launch

- [ ] Phase 118 audit: 90 PASS, 0 FAIL, 0 WARN
- [ ] Phase 117 audit: 168 PASS, 0 FAIL, 0 WARN
- [ ] Phase 119 beta launch readiness: all checks pass
- [ ] Message reality test: 7/7 PASS
- [ ] Full user flow test: 24 PASS, 0 FAIL
- [ ] ROLLBACK_PLAN.md reviewed and understood
- [ ] BETA_MONITORING_PLAN.md reviewed and understood
