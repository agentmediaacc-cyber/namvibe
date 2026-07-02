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

## Key files
- `templates/chain_home.html` — Main homepage template
- `static/css/namvibe_home_pro.css` — Premium homepage styles (nvpro- prefix)
- `static/css/namvibe_design_system.css` — Shared design tokens
- `static/js/namvibe_home_pro.js` — Premium homepage JS
- `static/css/namvibe_homepage_premium.css` — Phase 70 premium overrides (TikTok pink theme)

## Conventions
- Class prefixes: `nv-` (light theme, inline styles in chain_home.html), `nvpro-` (dark theme in namvibe_home_pro.css)
- SVG icons: 24x24 viewBox, `fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"`
- Template uses Jinja2 with Flask
- Homepage route: `GET /` in app.py with try/except guard
- CSRF: `meta[name="csrf-token"]` + `X-CSRFToken` header
- Toast: `window.NamVibeToast.show(msg)`, `window.NamVibeToast.success(msg)`
