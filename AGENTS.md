# Agent Guide — NamVibe

## Commands

### Run the app
```
python app.py
```

### Gunicorn
```
gunicorn app:app \
  --worker-class gevent \
  --workers 1 \
  --bind 0.0.0.0:8080 \
  --timeout 300 \
  --keep-alive 5
```

### Cloudflare tunnel
```
cloudflared tunnel --config ~/.cloudflared/config.yml run namvibe
```

### Run tests
```
python scripts/test_phase87e_homepage_no_500.py
python scripts/test_phase173_homepage_real_user_e2e.py --local
python scripts/test_phase174_homepage_timeout.py
python scripts/test_phase175_full_social_app_audit.py
python scripts/audit_homepage_real_actions.py
python scripts/test_homepage_click_hooks.py
python scripts/test_phase178_homepage_experience_engine.py
python scripts/test_phase179_social_interactions.py
python scripts/test_e2e_creator_content.py
```

### Restart services
```
pkill gunicorn && gunicorn app:app \
  --worker-class gevent \
  --workers 1 \
  --bind 0.0.0.0:8080 \
  --timeout 300 \
  --keep-alive 5
```

### Re-seed founder password (if needed)
```
python3 -c "
import os; os.environ['CHAIN_DISABLE_DB_PING']='1'; os.environ['CHAIN_FAST_LOCAL']='1'; os.environ['CHAIN_DISABLE_PREWARM']='1'
from services.neon_service import prime_neon_runtime, execute
from werkzeug.security import generate_password_hash
prime_neon_runtime()
h = generate_password_hash('namvibeadmin', method='pbkdf2:sha256')
execute(\"UPDATE chain_founder SET password_hash=%s, must_change_password=TRUE, is_first_login=TRUE, full_name='', email='', phone='' WHERE username='kaser'\", (h,), timeout_ms=30000)
print('Done')
"
```

## Live Platform — Files & Routes
- **Hub template**: `templates/live_hub.html` — Renders at `GET /live/`; 16 category sections (featured, friends, trending, music, gaming, business, shopping, church, education, government, health, sports, entertainment, new, scheduled) loaded dynamically by `NamVibeLive.initHub()`.
- **Room template**: `templates/live_room.html` — Renders at `GET /live/<id>`; full room with video area + sidebar (chat/participants/gifts/polls tabs), host controls, emoji picker integration.
- **CSS**: `static/css/namvibe_live.css` — 600+ lines: hub layout, category strip, live cards, go-live modal, room layout, video overlay, chat/gifts/participants/polls/products, gift animations, mobile responsive.
- **JS**: `static/js/namvibe_live.js` — 500+ lines: `NamVibeLive` global with `initHub()` (loads rooms by category, filter, go-live modal) and `initRoom()` (chat/polling/gifts/participants/polls/webcam/mic/cam toggle/end stream/polling).
- **API**: `api_routes/live_routes.py` — Blueprint at `/api/live/*` with endpoints: `rooms`, `scheduled`, `start`, `end`, `chat` (GET/POST), `gift`, `participants`, `polls`, `vote`, `products`, `stats`, `wallet/balance`, `wallet/transactions`, `wallet/purchase`, `wallet/packages`, `gifts`, `webrtc-config`, `livekit-token`, `livekit-status`, `turn-status`, `infra-health`.
- **DB schema**: `sql/phase_live.sql` — original schema (11 tables). `sql/phase_nvc_live.sql` — NVC system: `chain_nvc_wallet`, `chain_nvc_transactions`, `chain_live_gift_catalog` (58 gifts across 5 tiers). `sql/phase_config_tables.sql` — 10 config tables with seed data.

## Config API
- **Blueprint**: `api_routes/config_routes.py` at `/api/config/*` — 11 endpoints serving live config data from Neon DB (categories, gifts, gift tiers, live types, room types, interests, languages, creator types, notification types, reactions, bulk `all`)
- **DB tables**: `sql/phase_config_tables.sql` — 10 tables with seed data (chain_live_categories, chain_gift_tiers, chain_live_gift_catalog, chain_live_types, chain_room_types, chain_interests, chain_languages, chain_creator_types, chain_notification_types, chain_reaction_types)
- **Usage**: JS files (`namvibe_live.js`, `notifications_center.js`, `notifications_premium.js`) and onboarding template fetch config via `/api/config/all` or per-endpoint instead of hardcoded data
- **Test**: `scripts/test_e2e_creator_content.py` — 16/16 tests verifying content creation and public visibility

## Key files
- `templates/chain_home.html` — Main homepage template (now loads emoji picker + creative studio CSS/JS)
- `templates/live_hub.html` — Live Hub page template
- `templates/live_room.html` — Live Room page template
- `static/css/namvibe_home_pro.css` — Premium homepage styles (nvpro- prefix)
- `static/css/namvibe_design_system.css` — Shared design tokens
- `static/js/namvibe_home_pro.js` — Premium homepage JS
- `static/css/namvibe_homepage_premium.css` — Phase 70 premium overrides (TikTok pink theme)
- `static/css/namvibe_emoji_picker.css` — Emoji picker styles (dark glassmorphism, 9 categories, search)
- `static/js/namvibe_emoji_picker.js` — Unicode emoji picker (~1000 emojis, search, skin tones, `NamVibeEmojiPicker` global)
- `static/css/namvibe_creative_studio.css` — Creative studio styles (16 tool panels, sliders, grids, preview, mobile)
- `static/js/namvibe_creative_studio.js` — Creative studio (16 tools: camera/filters/adjust/AI/beauty/crop/transform/text/stickers/draw/music/video/effects/transitions/export/accessibility, drag-drop, `NamVibeCreativeStudio` global)
- `static/css/namvibe_live.css` — Live platform styles
- `static/js/namvibe_live.js` — Live platform JavaScript
- `api_routes/live_routes.py` — Live API blueprint (`/api/live/*`)
- `api_routes/founder_routes.py` — Founder dashboard blueprint (`/system/`)
- `services/founder_auth_service.py` — Founder auth (login, setup, password change)
- `services/founder_dashboard_service.py` — Live data queries from Neon
- `templates/founder/login.html` — Founder login page
- `templates/founder/setup.html` — First-login password change + personal details
- `templates/founder/dashboard.html` — Full system dashboard (all sections)
- `sql/phase_founder_dashboard.sql` — Table creation + seed for `chain_founder`
- `sql/phase_live.sql` — Live DB schema (10 tables + gift seeds)
- `sql/phase_config_tables.sql` — 10 config tables with seed data
- `api_routes/config_routes.py` — Config API blueprint (`/api/config/*`)
- `scripts/test_e2e_creator_content.py` — E2E creator content visibility tests

## Founder Dashboard
- URL: `http://localhost:8080/system/login`
- Default credentials: `kaser` / `namvibeadmin`
- First login forces password change + profile setup
- Sections: Overview, Users, Recruitment, Tasks, Finance, NVC Coins, Content, Reports, Messages, System Health, Security, Settings
- All data is live from Neon DB (real counts, real users, real transactions)
- Founder info update and password change via Settings section
- API endpoints at `/system/api/*` (JSON)

## Conventions
- Class prefixes: `nv-` (light theme, inline styles in chain_home.html), `nvpro-` (dark theme in namvibe_home_pro.css), `lv-` (live platform in namvibe_live.css)
- SVG icons: 24x24 viewBox, `fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"`
- Template uses Jinja2 with Flask
- Homepage route: `GET /` in app.py with try/except guard
- Live hub route: `GET /live/` in app.py; live room: `GET /live/<id>`
- CSRF: `meta[name="csrf-token"]` + `X-CSRFToken` header
- Toast: `window.NamVibeToast.show(msg)`, `window.NamVibeToast.success(msg)`
- Emoji picker: `NamVibeEmojiPicker.show(button, callback)` — reusable across reactions, comments, chat
- Creative studio: `NamVibeCreativeStudio.open(file?)` — overlay modal
- Live: `NamVibeLive.initHub()` / `NamVibeLive.initRoom(roomId, isHost)`

## Infrastructure & Live Engine Stack

### Database
- **Neon (PostgreSQL)** — `services/neon_service.py`: connection pool, circuit breaker, schema caching, SSL failover. Health at `GET /health/db`.
- **Supabase** (optional) — `supabase` package installed, client in `services/supabase_service.py`.

### Redis
- **Redis** — `services/redis_service.py`: connection manager, memory fallback, health at `GET /health/redis`. Required for Socket.IO multi-node and live presence.

### Real-time
- **Socket.IO** — `services/socketio_service.py`: `emit_to_live_room(room_id, event, payload)` for live events. Handlers registered: `live:join`, `live:leave`, `live:gift`, `live:reaction`, `live:raise_hand`, `live:ring`, `live:accept_call`, `live:reject_call`, `live:invite_guest`, `live:typing`, `live:mute`, `live:webrtc_offer/answer/ice`.

### WebRTC SFU
- **LiveKit** — `services/livekit_service.py`: token generation (host/viewer/guest), STUN/TURN config, server health check. API at `POST /api/live/livekit-token` and `GET /api/live/livekit-status`. Set `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `LIVEKIT_HOST`.

### NAT Traversal
- **coturn** — `services/turn_service.py`: STUN/TURN config object for WebRTC ICE. Google STUN built-in. Set `TURN_URL`, `TURN_USERNAME`, `TURN_CREDENTIAL` for TURN relay.

### Video Recording
- **FFmpeg** — installed via `brew install ffmpeg` or `apt install ffmpeg`. Used for stream recording, replay, clip generation.

### Connectivity Check
- `python scripts/check_connectivity.py` — validates all services (Neon, Redis, LiveKit, coturn, FFmpeg, packages).

### Endpoints
| Route | Purpose |
|-------|---------|
| `GET /api/live/webrtc-config` | ICE servers for WebRTC |
| `POST /api/live/livekit-token` | Get LiveKit JWT token |
| `GET /api/live/livekit-status` | LiveKit server health |
| `GET /api/live/turn-status` | TURN/STUN config status |
| `GET /api/live/infra-health` | All live infra health |
| `GET /health/db` | Neon DB health |
| `GET /health/redis` | Redis health |
| `GET /health/realtime` | Socket.IO health |
