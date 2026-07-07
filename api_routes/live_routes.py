"""NamVibe Live — API Routes (NVC Coin Powered, UUID)"""

import os
import time
from flask import Blueprint, request, jsonify, session, render_template
from services.neon_service import execute, fetch_all, fetch_one

live_bp = Blueprint("live", __name__, url_prefix="/api/live")

def _profile_id():
    pid = session.get("profile_id")
    if pid:
        return pid
    try:
        from services.profile_service import get_current_profile
        p = get_current_profile()
        if p and p.get("id"):
            return p["id"]
    except Exception:
        pass
    return session.get("auth_user_id")

# ─── NVC COIN HELPERS ─────────────────────────────────────
def _ensure_wallet(pid):
    execute(
        "INSERT INTO chain_nvc_wallet (profile_id, balance) VALUES (%s, 0) ON CONFLICT (profile_id) DO NOTHING",
        (pid,)
    )

def _get_balance(pid):
    _ensure_wallet(pid)
    row = fetch_one("SELECT balance FROM chain_nvc_wallet WHERE profile_id = %s", (pid,))
    return float(row["balance"]) if row else 0.0

def _deduct_nvc(pid, amount, ref_type="", ref_id="", desc=""):
    _ensure_wallet(pid)
    bal = _get_balance(pid)
    if bal < amount:
        return False, bal
    new_bal = bal - amount
    execute("UPDATE chain_nvc_wallet SET balance = %s, lifetime_spent = lifetime_spent + %s, updated_at = NOW() WHERE profile_id = %s",
            (new_bal, amount, pid))
    execute(
        "INSERT INTO chain_nvc_transactions (profile_id, type, amount, balance_after, reference_type, reference_id, description) VALUES (%s, 'gift_sent', %s, %s, %s, %s, %s)",
        (pid, -amount, new_bal, ref_type, ref_id, desc)
    )
    return True, new_bal

def _credit_nvc(pid, amount, tx_type, ref_type="", ref_id="", desc=""):
    _ensure_wallet(pid)
    bal = _get_balance(pid)
    new_bal = bal + amount
    execute("UPDATE chain_nvc_wallet SET balance = %s, lifetime_earned = lifetime_earned + %s, updated_at = NOW() WHERE profile_id = %s",
            (new_bal, amount, pid))
    execute(
        "INSERT INTO chain_nvc_transactions (profile_id, type, amount, balance_after, reference_type, reference_id, description) VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (pid, tx_type, amount, new_bal, ref_type, ref_id, desc)
    )

# ─── NVC BALANCE ──────────────────────────────────────────
@live_bp.route("/wallet/balance", methods=["GET"])
def wallet_balance():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    bal = _get_balance(pid)
    row = fetch_one(
        "SELECT lifetime_earned, lifetime_spent FROM chain_nvc_wallet WHERE profile_id = %s",
        (pid,)
    )
    return jsonify({
        "ok": True,
        "balance": bal,
        "lifetime_earned": float(row["lifetime_earned"]) if row else 0,
        "lifetime_spent": float(row["lifetime_spent"]) if row else 0,
    })

# ─── NVC TRANSACTIONS ─────────────────────────────────────
@live_bp.route("/wallet/transactions", methods=["GET"])
def wallet_transactions():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    limit = min(int(request.args.get("limit", 20)), 50)
    rows = fetch_all(
        "SELECT * FROM chain_nvc_transactions WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s",
        (pid, limit), default=[]
    )
    txs = []
    for r in rows:
        txs.append({
            "id": r["id"],
            "type": r.get("type", ""),
            "amount": float(r.get("amount", 0)),
            "balance_after": float(r.get("balance_after", 0)),
            "reference_type": r.get("reference_type", ""),
            "description": r.get("description", ""),
            "created_at": r.get("created_at").isoformat() if r.get("created_at") else "",
        })
    return jsonify({"transactions": txs})

# ─── PURCHASE NVC COINS ───────────────────────────────────
@live_bp.route("/wallet/purchase", methods=["POST"])
def purchase_coins():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    data = request.get_json() or {}
    package_id = data.get("package_id")
    if not package_id:
        return jsonify({"ok": False, "error": "Missing package_id"}), 400
    pkg = fetch_one(
        "SELECT * FROM chain_nvc_packages WHERE id = %s",
        (package_id,)
    )
    if not pkg:
        return jsonify({"ok": False, "error": "Package not found"}), 404
    total_coins = float(pkg["coins"]) + float(pkg.get("bonus_coins", 0))
    _credit_nvc(pid, total_coins, "purchase", "package", str(package_id),
                f"Purchased {pkg['name']} — {int(pkg['coins'])} + {int(pkg.get('bonus_coins',0))} bonus NVC")
    return jsonify({
        "ok": True,
        "coins_added": total_coins,
        "package_name": pkg["name"],
        "new_balance": _get_balance(pid),
    })

# ─── PURCHASE PACKAGES ────────────────────────────────────
@live_bp.route("/wallet/packages", methods=["GET"])
def get_packages():
    rows = fetch_all(
        "SELECT * FROM chain_nvc_packages ORDER BY sort_order ASC",
        (), default=[]
    )
    packages = []
    for r in rows:
        packages.append({
            "id": r["id"],
            "name": r.get("name", ""),
            "coins": float(r.get("coins", 0)),
            "bonus_coins": float(r.get("bonus_coins", 0)),
            "total_coins": float(r.get("coins", 0)) + float(r.get("bonus_coins", 0)),
            "price": float(r.get("price", 0)),
            "currency": r.get("currency", "NAD"),
            "is_popular": r.get("is_popular", False),
            "badge": r.get("badge", ""),
        })
    return jsonify({"packages": packages})

# ─── GET ROOMS ─────────────────────────────────────────────
@live_bp.route("/rooms", methods=["GET"])
def get_rooms():
    cat = request.args.get("category", "")
    limit = min(int(request.args.get("limit", 12)), 50)
    pid = _profile_id()

    base_cols = "r.id, r.profile_id, r.title, r.category, r.status, r.viewer_count, r.is_live, r.cover_url, r.thumbnail_url, p.display_name, p.username, p.avatar_url, p.is_verified"

    if cat == "friends" and pid:
        rows = fetch_all(
            """SELECT %s FROM chain_live_rooms r
               JOIN chain_follows f ON f.following_profile_id = r.profile_id
               JOIN chain_profiles p ON p.id = r.profile_id
               WHERE f.follower_profile_id = %%s AND r.is_live = TRUE
               ORDER BY r.viewer_count DESC LIMIT %%s""" % base_cols,
            (pid, limit), default=[]
        )
    elif cat and cat not in ("all", "new", "scheduled", "featured", "trending", "friends"):
        rows = fetch_all(
            """SELECT %s FROM chain_live_rooms r
               JOIN chain_profiles p ON p.id = r.profile_id
               WHERE r.category = %%s AND r.is_live = TRUE
               ORDER BY r.viewer_count DESC LIMIT %%s""" % base_cols,
            (cat, limit), default=[]
        )
    elif cat == "featured":
        rows = fetch_all(
            """SELECT %s FROM chain_live_rooms r
               JOIN chain_profiles p ON p.id = r.profile_id
               WHERE r.is_live = TRUE
               ORDER BY r.viewer_count DESC LIMIT %%s""" % base_cols,
            (limit,), default=[]
        )
    elif cat == "new":
        rows = fetch_all(
            """SELECT %s FROM chain_live_rooms r
               JOIN chain_profiles p ON p.id = r.profile_id
               WHERE r.is_live = TRUE
               ORDER BY r.created_at DESC LIMIT %%s""" % base_cols,
            (limit,), default=[]
        )
    else:
        rows = fetch_all(
            """SELECT %s FROM chain_live_rooms r
               JOIN chain_profiles p ON p.id = r.profile_id
               WHERE r.is_live = TRUE
               ORDER BY r.viewer_count DESC LIMIT %%s""" % base_cols,
            (limit,), default=[]
        )

    rooms = []
    for r in rows:
        rooms.append({
            "id": r["id"],
            "title": r.get("title", ""),
            "category": r.get("category", ""),
            "status": "live" if r.get("is_live") else r.get("status", "offline"),
            "viewer_count": r.get("viewer_count", 0),
            "host_name": r.get("display_name") or r.get("username") or "Host",
            "host_username": r.get("username", ""),
            "host_avatar": r.get("avatar_url") or "",
            "is_verified": r.get("is_verified", False),
            "thumbnail_url": r.get("cover_url") or r.get("thumbnail_url") or "",
            "is_featured": False,
        })
    return jsonify({"rooms": rooms, "count": len(rooms)})

# ─── GIFT CATALOG ─────────────────────────────────────────
@live_bp.route("/gifts", methods=["GET"])
def get_gift_catalog():
    tier = request.args.get("tier", "")
    if tier:
        rows = fetch_all(
            "SELECT * FROM chain_live_gift_catalog WHERE tier = %s ORDER BY price_nvc ASC",
            (tier,), default=[]
        )
    else:
        rows = fetch_all(
            "SELECT * FROM chain_live_gift_catalog ORDER BY sort_order ASC",
            (), default=[]
        )
    gifts = []
    for g in rows:
        gifts.append({
            "id": g["id"],
            "name": g.get("name", ""),
            "emoji": g.get("emoji", ""),
            "price_nvc": float(g.get("price_nvc", 0)),
            "tier": g.get("tier", "bronze"),
            "animation_class": g.get("animation_class", ""),
            "is_premium": g.get("is_premium", False),
            "is_featured": g.get("is_featured", False),
        })
    return jsonify({"gifts": gifts, "count": len(gifts)})

# ─── START LIVE ───────────────────────────────────────────
@live_bp.route("/start", methods=["POST"])
def start_live():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False, "error": "Not authenticated"}), 401

    data = request.get_json() or {}
    title = (data.get("title") or "Untitled Stream").strip()[:100]
    category = data.get("category", "entertainment")[:64]

    row = fetch_one(
        """INSERT INTO chain_live_rooms
           (profile_id, title, category, is_live, status)
           VALUES (%s, %s, %s, TRUE, 'live')
           RETURNING id""",
        (pid, title, category),
        timeout_ms=10000,
    )
    room_id = row["id"] if row else None
    if room_id:
        return jsonify({"ok": True, "room_id": room_id})
    return jsonify({"ok": False, "error": "Failed to create room"}), 500

# ─── SEND GIFT (NVC Coin Powered) ─────────────────────────
@live_bp.route("/<room_id>/gift", methods=["POST"])
def send_gift(room_id):
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401

    data = request.get_json() or {}
    gift_name = data.get("gift_name", "Heart")[:64]
    gift_emoji = data.get("gift_emoji", "❤️")[:16]
    amount = float(data.get("amount", 1))
    gift_catalog_id = data.get("gift_id", "")
    is_coin_gift = bool(data.get("is_coin_gift"))

    # Check NVC balance
    bal = _get_balance(pid)
    if bal < amount:
        return jsonify({
            "ok": False,
            "error": "Insufficient NVC coins",
            "balance": bal,
            "needed": amount,
            "shortfall": amount - bal,
        }), 402

    # Deduct NVC coins
    ok, new_bal = _deduct_nvc(pid, amount, "live_gift", room_id,
                       f"Sent {gift_emoji} {gift_name} ({amount} NVC) in room #{room_id}")
    if not ok:
        return jsonify({"ok": False, "error": "Transaction failed"}), 500

    # Record gift in existing chain_live_gifts table
    execute(
        "INSERT INTO chain_live_gifts (room_id, sender_profile_id, gift_name, gift_icon, amount) VALUES (%s, %s, %s, %s, %s)",
        (room_id, pid, gift_name, gift_emoji, amount)
    )

    # Update room gift_value increment
    execute(
        "UPDATE chain_live_rooms SET reaction_count = COALESCE(reaction_count, 0) + 1 WHERE id = %s",
        (room_id,)
    )

    return jsonify({
        "ok": True,
        "new_balance": new_bal,
    })

# ─── SCHEDULED ─────────────────────────────────────────────
@live_bp.route("/scheduled", methods=["GET"])
def get_scheduled():
    limit = min(int(request.args.get("limit", 12)), 50)
    rows = fetch_all(
        """SELECT r.id, r.profile_id, r.title, r.category, r.status, r.cover_url, r.thumbnail_url,
                  r.scheduled_at, p.display_name, p.username, p.avatar_url, p.is_verified
           FROM chain_live_rooms r
           JOIN chain_profiles p ON p.id = r.profile_id
           WHERE r.status = 'scheduled'
           ORDER BY r.scheduled_at ASC LIMIT %s""",
        (limit,), default=[]
    )
    rooms = []
    for r in rows:
        rooms.append({
            "id": r["id"],
            "title": r.get("title", ""),
            "category": r.get("category", ""),
            "status": "scheduled",
            "host_name": r.get("display_name") or r.get("username") or "Host",
            "host_avatar": r.get("avatar_url") or "",
            "is_verified": r.get("is_verified", False),
            "thumbnail_url": r.get("cover_url") or r.get("thumbnail_url") or "",
        })
    return jsonify({"rooms": rooms, "count": len(rooms)})

# ─── END LIVE ──────────────────────────────────────────────
@live_bp.route("/<room_id>/end", methods=["POST"])
def end_live(room_id):
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    room = fetch_one("SELECT profile_id FROM chain_live_rooms WHERE id = %s", (room_id,))
    if not room or str(room["profile_id"]) != str(pid):
        return jsonify({"ok": False, "error": "Not authorized"}), 403
    execute(
        "UPDATE chain_live_rooms SET is_live = FALSE, status = 'ended', ended_at = NOW() WHERE id = %s",
        (room_id,)
    )
    return jsonify({"ok": True})

# ─── CHAT ──────────────────────────────────────────────────
@live_bp.route("/<room_id>/chat", methods=["GET", "POST"])
def chat(room_id):
    pid = _profile_id()

    if request.method == "POST":
        if not pid:
            return jsonify({"ok": False}), 401
        data = request.get_json() or {}
        body = (data.get("body") or "").strip()[:500]
        if not body:
            return jsonify({"ok": False, "error": "Empty message"}), 400
        profile = fetch_one("SELECT display_name, username FROM chain_profiles WHERE id = %s", (pid,))
        if not profile:
            return jsonify({"ok": False, "error": "Profile not found"}), 404
        execute(
            "INSERT INTO chain_live_chat_messages (room_id, profile_id, display_name, body) VALUES (%s, %s, %s, %s)",
            (room_id, pid, profile.get("display_name") or profile.get("username") or "User", body)
        )
        return jsonify({
            "ok": True,
            "message": {
                "sender_name": profile.get("display_name") or profile.get("username") or "User",
                "body": body,
                "message_type": "text",
            }
        })

    after = request.args.get("after", 0, type=int)
    limit = min(int(request.args.get("limit", 50)), 100)
    rows = fetch_all(
        "SELECT id, profile_id, display_name, body, is_pinned, created_at FROM chain_live_chat_messages WHERE room_id = %s ORDER BY created_at ASC LIMIT %s",
        (room_id, limit), default=[]
    )
    messages = []
    for r in rows:
        messages.append({
            "id": r["id"],
            "sender_name": r.get("display_name", "User"),
            "body": r.get("body", ""),
            "is_pinned": r.get("is_pinned", False),
        })
    return jsonify({"messages": messages, "count": len(messages)})

# ─── PARTICIPANTS ──────────────────────────────────────────
@live_bp.route("/<room_id>/participants", methods=["GET"])
def get_participants(room_id):
    limit = min(int(request.args.get("limit", 50)), 100)
    rows = fetch_all(
        """SELECT lp.profile_id, lp.role, lp.joined_at,
                  COALESCE(p.display_name, p.username, 'User') AS display_name,
                  p.username, p.avatar_url
           FROM chain_live_participants lp
           JOIN chain_profiles p ON p.id = lp.profile_id
           WHERE lp.room_id = %s
           ORDER BY lp.joined_at ASC LIMIT %s""",
        (room_id, limit), default=[]
    )
    participants = []
    for r in rows:
        participants.append({
            "id": r["profile_id"],
            "display_name": r.get("display_name", "User"),
            "username": r.get("username", ""),
            "avatar_url": r.get("avatar_url", ""),
            "role": r.get("role", "viewer"),
        })
    return jsonify({"participants": participants, "count": len(participants)})

# ─── POLLS ─────────────────────────────────────────────────
@live_bp.route("/<room_id>/polls", methods=["GET"])
def get_polls(room_id):
    rows = fetch_all(
        "SELECT * FROM chain_live_polls WHERE room_id = %s AND is_active = TRUE ORDER BY created_at DESC LIMIT 5",
        (room_id,), default=[]
    )
    polls = []
    for r in rows:
        polls.append({
            "id": r["id"],
            "question": r.get("question", ""),
            "options": r.get("options") or [],
            "votes": r.get("votes") or [],
            "is_active": r.get("is_active", True),
        })
    return jsonify({"polls": polls})

# ─── VOTE ──────────────────────────────────────────────────
@live_bp.route("/<room_id>/vote", methods=["POST"])
def vote(room_id):
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    data = request.get_json() or {}
    poll_id = data.get("poll_id")
    option = data.get("option")
    if poll_id is None or option is None:
        return jsonify({"ok": False, "error": "Missing poll_id or option"}), 400
    option = int(option)
    poll = fetch_one("SELECT votes FROM chain_live_polls WHERE id = %s AND room_id = %s",
                     (poll_id, room_id))
    if not poll:
        return jsonify({"ok": False, "error": "Poll not found"}), 404
    votes = poll.get("votes") or []
    while len(votes) <= option:
        votes.append(0)
    votes[option] = (votes[option] or 0) + 1
    execute("UPDATE chain_live_polls SET votes = %s WHERE id = %s", (votes, poll_id))
    return jsonify({"ok": True})

# ─── PRODUCTS ──────────────────────────────────────────────
@live_bp.route("/<room_id>/products", methods=["GET"])
def get_products(room_id):
    rows = fetch_all(
        "SELECT * FROM chain_live_products WHERE room_id = %s ORDER BY sort_order ASC LIMIT 20",
        (room_id,), default=[]
    )
    products = []
    for r in rows:
        products.append({
            "id": r["id"],
            "title": r.get("title", ""),
            "price": float(r.get("price", 0)),
            "currency": r.get("currency", "NAD"),
            "image_url": r.get("image_url", ""),
            "discount_pct": r.get("discount_pct", 0),
        })
    return jsonify({"products": products})

# ─── STATS ─────────────────────────────────────────────────
@live_bp.route("/<room_id>/stats", methods=["GET"])
def get_stats(room_id):
    room = fetch_one(
        "SELECT viewer_count, peak_viewer_count, likes_count, reaction_count FROM chain_live_rooms WHERE id = %s",
        (room_id,)
    )
    participant_count = fetch_one(
        "SELECT COUNT(*) AS cnt FROM chain_live_participants WHERE room_id = %s",
        (room_id,)
    )
    return jsonify({
        "viewer_count": room["viewer_count"] if room else 0,
        "peak_viewers": room["peak_viewer_count"] if room else 0,
        "like_count": room["likes_count"] if room else 0,
        "gift_value": float(room["reaction_count"]) if room else 0,
        "participant_count": participant_count["cnt"] if participant_count else 0,
    })

# ─── WEBRTC / LIVEKIT CONFIG ──────────────────────────────
@live_bp.route("/webrtc-config", methods=["GET"])
def webrtc_config():
    from services.turn_service import get_turn_config
    return jsonify(get_turn_config())

@live_bp.route("/livekit-token", methods=["POST"])
def request_livekit_token():
    pid = _profile_id()
    if not pid:
        return jsonify({"ok": False}), 401
    data = request.get_json() or {}
    room_name = data.get("room_name", f"room_{int(time.time())}")
    identity = data.get("identity", f"user_{pid[:8]}")
    role = data.get("role", "viewer")
    from services.livekit_service import create_ingress_token, create_viewer_token, create_guest_token
    if role == "host":
        token = create_ingress_token(identity, room_name)
    elif role == "guest":
        token = create_guest_token(identity, room_name)
    else:
        token = create_viewer_token(identity, room_name)
    if not token:
        return jsonify({"ok": False, "error": "LiveKit not configured"}), 503
    LIVEKIT_WS_URL = os.environ.get("LIVEKIT_WS_URL", "").strip()
    return jsonify({"ok": True, "token": token, "ws_url": LIVEKIT_WS_URL})


# ─── LIVEKIT STATUS ───────────────────────────────────────
@live_bp.route("/livekit-status", methods=["GET"])
def livekit_status():
    from services.livekit_service import get_livekit_server_info, check_livekit_health
    info = get_livekit_server_info()
    health = check_livekit_health()
    return jsonify({**info, **health})


# ─── TURN STATUS ──────────────────────────────────────────
@live_bp.route("/turn-status", methods=["GET"])
def turn_status():
    from services.turn_service import get_turn_status
    return jsonify(get_turn_status())


# ─── FULL LIVE INFRA HEALTH ───────────────────────────────
@live_bp.route("/infra-health", methods=["GET"])
def infra_health():
    from services.neon_service import get_neon_health
    from services.redis_service import get_redis_health, redis_available
    from services.livekit_service import check_livekit_health, get_livekit_server_info
    from services.turn_service import get_turn_status

    neon = get_neon_health()
    redis_h = get_redis_health()
    lk = check_livekit_health()
    turn = get_turn_status()

    all_ok = (
        neon.get("status") in ("ok", "disabled") and
        redis_h.get("available") is not False and
        lk.get("status") in ("ok", "not_configured")
    )

    return jsonify({
        "ok": all_ok,
        "neon": {"status": neon.get("status"), "connected": neon.get("connected", False)},
        "redis": {"available": redis_h.get("available", False), "status": redis_h.get("status")},
        "livekit": {"status": lk.get("status"), "configured": get_livekit_server_info().get("configured", False)},
        "turn": {"configured": turn.get("configured", False)},
    })


# ─── REGISTER BLUEPRINT ─────────────────────────────────────
def register_live_routes(app):
    app.register_blueprint(live_bp)
    print("[live] Live API routes registered (NVC + WebRTC + LiveKit + coturn)")
