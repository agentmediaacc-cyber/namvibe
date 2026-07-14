# NamVibe Active Feature Map

This document records the currently active Flask route, template, service, JavaScript, CSS, and database entrypoints for the main social surfaces.

Evidence basis:
- `app.py` blueprint registrations and the `/` route render path
- `app.url_map` route audit
- route module imports and template references
- homepage JS/template source inspection

## Homepage
- Blueprint names: `homepage_api`, `feed_preload`
- Route files: `app.py`, `api_routes/homepage_api.py`
- URL prefixes: `/`, `/api/homepage/*`, `/api/home/*`
- Endpoint count: 16 registered homepage-related routes (`/` plus 15 API routes across `api_routes/homepage_api.py` and `feed_preload`)
- Service files: `services/homepage_service.py`, `services/homepage_phase141_service.py`, `services/homepage_warmup_service.py`, `services/homepage_real_data_guard.py`, `services/feed_ranking_service.py`
- Template: `templates/chain_home.html`
- Frontend JS: `static/js/namvibe_home_pro.js`
- Frontend CSS: `static/css/namvibe_home_pro.css`, `static/css/namvibe_home_premium_v2.css`, `static/css/namvibe_creative_studio.css`, `static/css/namvibe_emoji_picker.css`
- Database tables: `chain_posts`, `chain_reels`, `chain_stories`, `chain_status_posts`, `chain_live_rooms`, `chain_profiles`, `chain_marketplace_items`
- Duplicate/legacy entrypoints: `static/js/namvibe_home_premium_v2.js` remains present but is not loaded by `templates/chain_home.html`
- Active implementation: `templates/chain_home.html` with `static/js/namvibe_home_pro.js`
- Evidence: template contains one homepage controller include; `static/js/namvibe_home_pro.js` has `window.__NAMVIBE_HOME_PRO_INITIALIZED__` guard

## Posts
- Blueprint names: `homepage_api`, `post_bp`, `feed_bp`
- Route files: `api_routes/homepage_api.py`, `api_routes/post_routes.py`, `api_routes/feed_routes.py`
- URL prefixes: `/api/home/*`, `/posts/*`, `/api/feed/*`
- Endpoint count: 18 registered post/feed routes across `api_routes/homepage_api.py`, `api_routes/feed_routes.py`, `api_routes/post_routes.py`, and `api_routes/engagement_routes.py`
- Service files: `services/homepage_service.py`, `services/feed_engine.py`, `services/engagement_service.py`, `services/content_service.py`
- Templates: `templates/chain_home.html`, post-specific templates
- Frontend JS: `static/js/namvibe_home_pro.js`
- CSS: `static/css/namvibe_home_pro.css`
- Database tables: `chain_posts`, `chain_post_likes`, `chain_post_comments`, `chain_post_saves`
- Duplicate/legacy entrypoints: `api_routes/feed_routes.py` and homepage feed endpoints overlap intentionally by purpose
- Active implementation: homepage social feed + post action APIs
- Evidence: homepage feed renders post cards and routes like/save/share/comment through `/api/home/post/...`

## Status
- Blueprint names: `status_bp`
- Route files: `api_routes/status_routes.py`
- URL prefixes: `/status/*`
- Endpoint count: 7 registered status routes
- Service files: `services/status_service.py`, `services/homepage_service.py`
- Templates: `templates/status/detail.html`
- Frontend JS: `static/js/status_autoplay_engine.js`
- CSS: `static/css/stories.css`, `static/css/home_feed_mobile.css`, homepage shared styles where used
- Database tables: `chain_status_posts`
- Duplicate/legacy entrypoints: homepage may surface status content alongside dedicated status routes
- Active implementation: dedicated status routes plus homepage status feed integration
- Evidence: homepage payload includes `status_posts`, and status detail template exists

## Stories
- Blueprint names: `stories_v2_bp`
- Route files: `api_routes/stories_v2_routes.py`
- URL prefixes: `/stories/*`, `/api/stories/*` where implemented
- Endpoint count: 50 registered story routes
- Service files: `services/stories_engine.py`, `services/stories_service.py`, `services/story_engagement_service.py`
- Templates: `templates/stories.html`, `templates/stories/tray.html`
- Frontend JS: `static/js/namvibe_stories_engine.js`, `static/js/namvibe_stories_pro.js`
- CSS: `static/css/stories.css`, `static/css/namvibe_stories_engine.css`
- Database tables: `chain_stories`
- Duplicate/legacy entrypoints: older story tray variants may coexist with v2
- Active implementation: `api_routes/stories_v2_routes.py` and homepage stories tray rendering
- Evidence: homepage payload and template both include story data

## Reels
- Blueprint names: `reels_bp`
- Route files: `api_routes/reels_routes.py`
- URL prefixes: `/reels/*`, `/reels/api/*`
- Endpoint count: 28 registered reel routes
- Service files: `services/reels_engine.py`, `services/reels_service.py`
- Templates: `templates/reels.html`, `templates/reels/index.html`
- Frontend JS: `static/js/reels.js`, `static/js/reels_autoplay_engine.js`, `static/js/namvibe_reels_pro.js`
- CSS: `static/css/reels.css`, `static/css/namvibe_reels_engine.css`
- Database tables: `chain_reels`
- Duplicate/legacy entrypoints: older reel UI variants remain alongside the active route set
- Active implementation: `api_routes/reels_routes.py` plus homepage reel cards
- Evidence: homepage JS reads `data-video-url` cards and `/reels/api/reels/view/batch`

## Live
- Blueprint names: `live_bp`, `live_media_bp`
- Route files: `api_routes/live_routes.py`, `api_routes/live_media_routes.py`
- URL prefixes: `/live/*`, `/api/live/*`
- Endpoint count: 32 registered live routes
- Service files: `services/live_engine.py`, `services/live_service.py`, `services/livekit_service.py`, `services/turn_service.py`
- Templates: `templates/live_hub.html`, `templates/live_room.html`, `templates/live/index.html`
- Frontend JS: `static/js/namvibe_live.js`, `static/js/namvibe_live_engine.js`
- CSS: `static/css/namvibe_live.css`, `static/css/namvibe_live_engine.css`, `static/css/live.css`, `static/css/live_system.css`
- Database tables: `chain_live_rooms`, `chain_live_viewers`, `chain_live_comments`, `chain_live_gifts`, `chain_live_polls`
- Duplicate/legacy entrypoints: older live engine files coexist with the active live routes
- Active implementation: `api_routes/live_routes.py` with live room/hub templates
- Evidence: homepage stats link to `/live/`, homepage payload loads `live_rooms`

## Messages
- Blueprint names: `message_bp`, `messaging_api_bp`, `inbox_bp`
- Route files: `api_routes/message_routes.py`, `api_routes/messaging_routes.py`, `api_routes/inbox_routes.py`, `api_routes/message_production_routes.py`, `api_routes/message_upgrade_routes.py`
- URL prefixes: `/messages/*`, `/inbox/*`, `/api/messages/*`
- Endpoint count: 134 registered message routes
- Service files: `services/messaging_engine.py`, `services/message_thread_service.py`, `services/message_delivery_service.py`, `services/message_receipt_service.py`, `services/message_feature_service.py`
- Templates: `templates/messages/index.html`, `templates/messages/inbox.html`, `templates/messages/thread.html`
- Frontend JS: `static/js/namvibe_messages_pro.js`, `static/js/message_composer.js`, `static/js/message_premium_features.js`
- CSS: `static/css/namvibe_messages_pro.css`, `static/css/chat.css`, `static/css/message_requests.css`
- Database tables: message/thread tables referenced by the messaging services and routes
- Duplicate/legacy entrypoints: `messages/index.html` and `messages/inbox.html` both exist as entry surfaces
- Active implementation: `api_routes/message_routes.py` plus inbox/thread templates
- Evidence: inbox and thread templates render actual conversation state and contact search

## Calls
- Blueprint names: `call_bp`, `messages_call_bp`, `api_calls_bp`, `group_call_bp`
- Route files: `api_routes/call_routes.py`, `api_routes/group_call_routes.py`
- URL prefixes: `/calls/*`, `/api/calls/*`
- Endpoint count: 74 registered call routes
- Service files: `services/call_service.py`, `services/call_lifecycle_service.py`, `services/webrtc_call_service.py`, `services/group_call_service.py`, `services/call_feature_service.py`
- Templates: `templates/calls/index.html`, `templates/calls/video.html`, `templates/calls/history.html`, `templates/calls/group_call.html`
- Frontend JS: `static/js/webrtc_calls.js`, `static/js/namvibe_calls_pro.js`, `static/js/group_calls.js`
- CSS: `static/css/namvibe_calls_pro.css`, `static/css/calls.css`
- Database tables: call session, participant, event, and notification tables used by call services
- Duplicate/legacy entrypoints: multiple call implementations exist for p2p, group, and historical views
- Active implementation: `api_routes/call_routes.py` and `api_routes/group_call_routes.py`
- Evidence: homepage and profile navigation route to `/calls/` and call-specific templates exist

## Notifications
- Blueprint names: `notification_engine_bp`, `notification_center_bp`, `notification_bp` where registered
- Route files: `api_routes/notification_routes.py`, `api_routes/notification_center_routes.py`, `api_routes/push_notification_routes.py`
- URL prefixes: `/notifications/*`, `/api/notifications/*`
- Endpoint count: 32 registered notification routes
- Service files: `services/notification_engine.py`, `services/notification_center_service.py`, `services/notification_grouping_service.py`
- Templates: `templates/notifications/index.html`
- Frontend JS: `static/js/namvibe_notifications.js`, `static/js/notifications_center.js`, `static/js/notifications_premium.js`
- CSS: `static/css/namvibe_notifications.css`
- Database tables: notification tables in the notification services
- Duplicate/legacy entrypoints: premium and center variants coexist
- Active implementation: `templates/notifications/index.html` with `static/js/namvibe_notifications.js`
- Evidence: notifications page renders its own JS and no longer loads homepage controller JS

## Friend requests
- Blueprint names: `follow_request_api_bp`, `friend_bp`
- Route files: `api_routes/follow_request_routes.py`, `api_routes/friend_routes.py`
- URL prefixes: social follow/friend endpoints
- Endpoint count: 14 registered friend/follow-request routes
- Service files: `services/relationship_privacy_service.py`, `services/social_action_policy.py`
- Templates: profile relationship surfaces
- Frontend JS: `static/js/follow_request_controls.js`, `static/js/friendship_controls.js`
- CSS: profile and shared styles
- Database tables: friend/follow relationship tables
- Active implementation: follow/friend request routes and profile UI controls
- Evidence: homepage social actions point to these route families

## Profiles
- Blueprint names: `profile_bp`, `profile_extra_bp`
- Route files: `api_routes/profile_routes.py`, `api_routes/social_graph_routes.py`
- URL prefixes: `/profile/*`
- Endpoint count: 104 registered profile routes
- Service files: `services/profile_service.py`, `services/profile_view_service.py`, `services/profile_dashboard_service.py`
- Templates: `templates/profile/*`
- Frontend JS: `static/js/profile_systems.js`, `static/js/profile_premium.js`, `static/js/namvibe_profile_pro.js`
- CSS: `static/css/profile.css`, `static/css/profile_premium.css`, `static/css/namvibe_profile_premium.css`
- Database tables: profile tables and dashboard tables
- Duplicate/legacy entrypoints: multiple profile UIs exist for settings, dashboard, and public view
- Active implementation: profile route stack used by homepage avatars and profile links
- Evidence: homepage links profile cards and suggestions to `/profile/...`

## Discover
- Blueprint names: `discovery_bp`, `search_bp`
- Route files: `api_routes/discovery_routes.py`, `api_routes/search_routes.py`, `api_routes/explore_routes.py`
- URL prefixes: `/discover/*`, `/search/*`, `/explore/*`
- Endpoint count: 9 registered discover/search routes
- Service files: `services/discovery_service.py`, `services/search_service.py`, `services/recommendation_service.py`
- Templates: `templates/discover/index.html`, `templates/search/index.html`, `templates/explore.html`
- Frontend JS: `static/js/explore.js`
- CSS: `static/css/explore.css`, `static/css/discover_mobile.css`
- Database tables: discovery, recommendation, profile tables
- Active implementation: discover routes and homepage discover links
- Evidence: homepage menu and stats link to `/discover/`

## Dating
- Blueprint names: `dating_bp`, `connecting_you_bp`
- Route files: `api_routes/dating_routes.py`, `api_routes/connecting_you_routes.py`
- URL prefixes: `/dating/*`, `/connecting-you/*` or mapped route aliases
- Endpoint count: 58 registered dating routes
- Service files: `services/dating_service.py`, `services/connecting_you_service.py`
- Templates: `templates/dating/index.html`, `templates/dating/profile.html`, `templates/connecting_you/*`
- Frontend JS: `static/js/dating_premium.js`, `static/js/connecting_you.js`
- CSS: `static/css/matching.css`, `static/css/connecting_you.css`
- Database tables: dating/matching/enrollment/event tables
- Duplicate/legacy entrypoints: `dating` and `connecting you` overlap intentionally as adjacent surfaces
- Active implementation: both route families are live
- Evidence: homepage nav uses dating label and discovery fallback

## Connecting You
- Blueprint names: `connecting_you_bp`
- Route files: `api_routes/connecting_you_routes.py`
- URL prefixes: `/dating/connecting-you/*`, `/dating/admin/*`
- Endpoint count: 31 registered Connecting You routes
- Service files: `services/connecting_you_service.py`
- Templates: `templates/connecting_you/*`
- Frontend JS: `static/js/connecting_you.js`
- CSS: `static/css/connecting_you.css`
- Database tables: connecting-you tables in `sql/phase_connecting_you.sql`
- Duplicate/legacy entrypoints: may overlap with dating routes by product definition
- Active implementation: route registration in `app.py`
- Evidence: module exists and is imported during app startup

## Wallet
- Blueprint names: `wallet_bp`
- Route files: `api_routes/wallet_routes.py`
- URL prefixes: `/wallet/*`
- Endpoint count: 32 registered wallet routes
- Service files: `services/wallet_*` and related wallet helpers
- Templates: `templates/wallet/index.html`, `templates/wallet/creator_earnings.html`
- Frontend JS: `static/js/namvibe_wallet_pro.js`, `static/js/wallet_premium.js`
- CSS: `static/css/namvibe_wallet_pro.css`, `static/css/wallet.css`, `static/css/wallet_premium.css`
- Database tables: wallet/transactions/package tables
- Active implementation: wallet route family and homepage wallet links
- Evidence: homepage nav links to `/wallet/`

## Advertising
- Blueprint names: `advertising_bp`, `ad_admin_bp`
- Route files: `api_routes/advertising_routes.py`, `api_routes/ad_admin_routes.py`
- URL prefixes: ad/admin route families
- Endpoint count: 31 registered advertising routes
- Service files: ad and monetization services
- Templates: ad/admin templates
- Frontend JS: ad management JS where applicable
- CSS: ad/admin styles
- Database tables: ad campaign and placement tables
- Active implementation: admin/advertising route family
- Evidence: dedicated route modules exist and are imported by `app.py`

## Marketplace
- Blueprint names: `marketplace_bp`
- Route files: `api_routes/marketplace_routes.py`
- URL prefixes: `/marketplace/*`
- Endpoint count: 23 registered marketplace routes
- Service files: marketplace services
- Templates: `templates/marketplace/dashboard.html`
- Frontend JS: marketplace JS where applicable
- CSS: marketplace CSS where applicable
- Database tables: marketplace item tables
- Active implementation: marketplace route family and homepage quick links
- Evidence: homepage sidebar links to `/marketplace/`

## Creator tools
- Blueprint names: `creator_bp`, `studio_bp`
- Route files: `api_routes/creator_routes.py`, `api_routes/creator_studio_routes.py`
- URL prefixes: creator/studio route families
- Endpoint count: 21 registered creator-tool routes
- Service files: `services/creator_*` and studio services
- Templates: `templates/creator/*`, `templates/profile/creator_tools.html`
- Frontend JS: `static/js/creator_premium.js`, `static/js/namvibe_creative_studio.js`
- CSS: `static/css/creator_premium.css`, `static/css/namvibe_creative_studio.css`
- Database tables: creator tool tables and content tables
- Active implementation: creator route family
- Evidence: creator tools pages and creative studio assets are present

## Settings
- Blueprint names: profile/security/privacy/system route families
- Route files: `api_routes/profile_routes.py`, `api_routes/security_routes.py`, `api_routes/privacy_routes.py`, `api_routes/system_routes.py`
- URL prefixes: `/profile/settings`, `/privacy`, `/security`, `/system/*`
- Endpoint count: 57 registered settings/security/privacy routes
- Service files: profile/security/privacy services
- Templates: `templates/profile/settings.html`, privacy/security templates
- Frontend JS: settings/profile JS where applicable
- CSS: profile/settings styles where applicable
- Database tables: profile preferences and security tables
- Active implementation: profile and security route families
- Evidence: homepage menu links to profile settings
