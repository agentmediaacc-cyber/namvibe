"""
NamVibe Advertising Platform — Complete service layer.
Handles: campaigns, creatives, placements, targeting, analytics,
payments, moderation, fraud detection, coupons, promotions, ad serving.
"""
import uuid
import json
import time
import random
import hashlib
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, date, timezone, timedelta
from services.neon_service import fast_query, write_query, transaction_query

# ── Helpers ──────────────────────────────────────────────────────────

def _utcnow():
    return datetime.now(timezone.utc)

def _today():
    return date.today()

def _uuid():
    return str(uuid.uuid4())

_TWOPLACES = Decimal("0.01")

def _as_decimal(value, default="0"):
    try:
        if value in (None, ""):
            return Decimal(default)
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)

def _money_to_cents(value):
    quantized = _as_decimal(value).quantize(_TWOPLACES, rounding=ROUND_HALF_UP)
    return int(quantized * 100)

def _cents_to_money(cents):
    return (Decimal(int(cents)) / Decimal("100")).quantize(_TWOPLACES)

def _normalize_campaign_money_fields(row):
    if not row:
        return row
    row["budget_cents"] = int(row.get("budget_cents") or _money_to_cents(row.get("budget", 0)))
    row["daily_budget_cents"] = int(row.get("daily_budget_cents") or _money_to_cents(row.get("daily_budget", 0)))
    row["bid_amount_cents"] = int(row.get("bid_amount_cents") or _money_to_cents(row.get("bid_amount", 0)))
    row["spent_amount_cents"] = int(row.get("spent_amount_cents") or _money_to_cents(row.get("spent_amount", 0)))
    row["funded_amount_cents"] = int(row.get("funded_amount_cents") or 0)
    row["daily_spend_cents"] = int(row.get("daily_spend_cents") or 0)
    return row

def _campaign_status_allows_funding(status):
    return status in {"draft", "pending_payment"}

def _campaign_status_is_chargeable(status):
    return status == "active"

def _campaign_status_for_funding(campaign):
    if int(campaign.get("funded_amount_cents") or 0) > 0:
        return "funded"
    return "pending_payment"

def _normalize_idempotency_key(prefix, key, *parts):
    if key:
        return str(key)
    return f"{prefix}:{':'.join(str(part) for part in parts)}"

def normalize_fraud_event_details(details):
    if details is None:
        return {"click_id": None, "flags": []}
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except Exception:
            return {"click_id": None, "flags": []}
    if isinstance(details, list):
        flags = [flag for flag in details if isinstance(flag, dict)]
        return {"click_id": None, "flags": flags}
    if isinstance(details, dict):
        click_id = details.get("click_id")
        if click_id is not None:
            click_id = str(click_id)
        flags = details.get("flags")
        if not isinstance(flags, list):
            flags = []
        flags = [flag for flag in flags if isinstance(flag, dict)]
        return {"click_id": click_id, "flags": flags}
    return {"click_id": None, "flags": []}

# In-memory ad serve dedup (per viewer per 60s window)
_AD_SERVE_CACHE = {}
_AD_DEDUP_TTL = 60

def _dedup_key(viewer_id):
    bucket = int(time.time() / _AD_DEDUP_TTL)
    return f"ad:{viewer_id}:{bucket}"

def _is_ad_served(ad_id, viewer_id):
    return ad_id in _AD_SERVE_CACHE.get(_dedup_key(viewer_id), set())

def _mark_ad_served(ad_id, viewer_id):
    key = _dedup_key(viewer_id)
    if key not in _AD_SERVE_CACHE:
        if len(_AD_SERVE_CACHE) > 2000:
            _AD_SERVE_CACHE.clear()
        _AD_SERVE_CACHE[key] = set()
    _AD_SERVE_CACHE[key].add(ad_id)

# ── Advertisers ──────────────────────────────────────────────────────

def get_or_create_advertiser(profile_id):
    rows = fast_query(
        "SELECT * FROM chain_advertisers WHERE profile_id = %s",
        (profile_id,), default=[]
    )
    if rows:
        return rows[0]
    pid = _uuid()
    try:
        write_query(
            "INSERT INTO chain_advertisers (id, profile_id) VALUES (%s, %s)",
            (pid, profile_id)
        )
        return {"id": pid, "profile_id": profile_id, "total_spent": 0, "lifetime_spent": 0}
    except Exception:
        return fast_query(
            "SELECT * FROM chain_advertisers WHERE profile_id = %s",
            (profile_id,), default=[{}]
        )[0]

def update_advertiser(profile_id, **kwargs):
    allowed = {"business_name","business_category","business_website",
               "business_description","tax_id","billing_email","billing_address"}
    safe = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if safe:
        sets = ", ".join(f'"{k}" = %s' for k in safe)
        vals = list(safe.values()) + [profile_id]
        write_query(f"UPDATE chain_advertisers SET {sets} WHERE profile_id = %s", vals)
    return {"ok": True}

# ── Campaigns ────────────────────────────────────────────────────────

def create_campaign(profile_id, title, objective="reach", ad_type="feed",
                    media_url=None, target_url=None, budget=0, daily_budget=0,
                    start_date=None, end_date=None, media_type="image",
                    category=None, bid_type="auto", bid_amount=0,
                    currency="NAD", target_audience=None):
    cid = _uuid()
    now = _utcnow()
    budget_cents = _money_to_cents(budget)
    daily_budget_cents = _money_to_cents(daily_budget)
    bid_amount_cents = _money_to_cents(bid_amount)
    try:
        write_query(
            """INSERT INTO chain_ad_campaigns
               (id, owner_id, title, objective, ad_type, content_url, target_url,
                budget, daily_budget, starts_at, ends_at, media_type, category,
                bid_type, bid_amount, currency, target_audience, status, created_at,
                budget_cents, daily_budget_cents, bid_amount_cents, funded_amount_cents, spent_amount_cents, daily_spend_cents)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft', %s, %s, %s, %s, 0, 0, 0)""",
            (cid, profile_id, title, objective, ad_type, media_url, target_url,
             budget, daily_budget, start_date or now, end_date, media_type,
             category, bid_type, bid_amount, currency,
             json.dumps(target_audience or {}), now, budget_cents, daily_budget_cents, bid_amount_cents)
        )
        return {"ok": True, "campaign_id": cid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_campaign(campaign_id):
    rows = fast_query(
        "SELECT c.*, p.username, p.display_name, p.avatar_url "
        "FROM chain_ad_campaigns c JOIN chain_profiles p ON c.owner_id = p.id "
        "WHERE c.id = %s AND c.is_deleted = FALSE",
        (campaign_id,), timeout_ms=3000, default=[]
    )
    return _normalize_campaign_money_fields(rows[0]) if rows else None

def get_campaigns_for_user(profile_id, limit=50):
    rows = fast_query(
        "SELECT * FROM chain_ad_campaigns WHERE owner_id = %s AND is_deleted = FALSE "
        "ORDER BY created_at DESC LIMIT %s",
        (profile_id, limit), default=[]
    )
    return [_normalize_campaign_money_fields(dict(row)) for row in rows]

def get_campaigns_for_admin(status=None, limit=100):
    if status:
        rows = fast_query(
            "SELECT c.*, p.username, p.display_name, p.avatar_url "
            "FROM chain_ad_campaigns c JOIN chain_profiles p ON c.owner_id = p.id "
            "WHERE c.status = %s AND c.is_deleted = FALSE ORDER BY c.created_at DESC LIMIT %s",
            (status, limit), default=[]
        )
        return [_normalize_campaign_money_fields(dict(row)) for row in rows]
    rows = fast_query(
        "SELECT c.*, p.username, p.display_name, p.avatar_url "
        "FROM chain_ad_campaigns c JOIN chain_profiles p ON c.owner_id = p.id "
        "WHERE c.is_deleted = FALSE ORDER BY c.created_at DESC LIMIT %s",
        (limit,), default=[]
    )
    return [_normalize_campaign_money_fields(dict(row)) for row in rows]

def update_campaign(campaign_id, profile_id=None, **kwargs):
    allowed = {"title","objective","ad_type","content_url","target_url",
               "budget","daily_budget","starts_at","ends_at","media_type",
               "category","bid_type","bid_amount","target_audience"}
    safe = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not safe:
        return {"ok": False, "error": "No valid fields to update"}
    sets = ", ".join(f'"{k}" = %s' for k in safe)
    vals = list(safe.values()) + [campaign_id]
    if profile_id:
        vals.append(profile_id)
        write_query(f"UPDATE chain_ad_campaigns SET {sets} WHERE id = %s AND owner_id = %s", vals)
    else:
        write_query(f"UPDATE chain_ad_campaigns SET {sets} WHERE id = %s", vals)
    return {"ok": True}

def duplicate_campaign(campaign_id, profile_id=None):
    original = get_campaign(campaign_id)
    if not original:
        return {"ok": False, "error": "Campaign not found"}
    nid = _uuid()
    now = _utcnow()
    try:
        write_query(
            """INSERT INTO chain_ad_campaigns
               (id, owner_id, title, objective, ad_type, content_url, target_url,
                budget, daily_budget, starts_at, ends_at, media_type, category,
                bid_type, bid_amount, currency, target_audience, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, 'draft', %s)""",
            (nid, profile_id or original["owner_id"],
             f"{original.get('title','')} (copy)", original.get("objective"),
             original.get("ad_type"), original.get("content_url"),
             original.get("target_url"), original.get("budget", 0),
             original.get("daily_budget", 0), now,
             original.get("ends_at"), original.get("media_type"),
             original.get("category"), original.get("bid_type"),
             original.get("bid_amount", 0), original.get("currency", "NAD"),
             original.get("target_audience", "{}"), now)
        )
        return {"ok": True, "campaign_id": nid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def delete_campaign(campaign_id, profile_id=None):
    if profile_id:
        write_query(
            "UPDATE chain_ad_campaigns SET is_deleted = TRUE WHERE id = %s AND owner_id = %s",
            (campaign_id, profile_id)
        )
    else:
        write_query(
            "UPDATE chain_ad_campaigns SET is_deleted = TRUE WHERE id = %s",
            (campaign_id,)
        )
    return {"ok": True}

def fund_campaign(campaign_id, owner_profile_id, idempotency_key=None):
    funding_key = _normalize_idempotency_key("ad-fund", idempotency_key, owner_profile_id, campaign_id)

    def _callback(cursor):
        cursor.execute(
            """
            SELECT p.id, p.status, p.amount_cents, p.wallet_transaction_id
            FROM chain_ad_payments p
            WHERE p.campaign_id = %s AND p.profile_id = %s AND p.idempotency_key = %s
            LIMIT 1
            """,
            (campaign_id, owner_profile_id, funding_key),
        )
        existing_payment = cursor.fetchone()
        cursor.execute(
            """
            SELECT *
            FROM chain_ad_campaigns
            WHERE id = %s AND owner_id = %s AND is_deleted = FALSE
            FOR UPDATE
            """,
            (campaign_id, owner_profile_id),
        )
        campaign = cursor.fetchone()
        if not campaign:
            return {"ok": False, "error": "campaign_not_found"}
        campaign = _normalize_campaign_money_fields(dict(campaign))
        if existing_payment and existing_payment.get("status") == "completed":
            if campaign.get("status") in {"funded", "pending_review", "active", "paused", "completed", "budget_exhausted"}:
                return {
                    "ok": True,
                    "idempotent": True,
                    "payment_id": str(existing_payment["id"]),
                    "wallet_transaction_id": str(existing_payment.get("wallet_transaction_id") or ""),
                    "campaign_status": campaign.get("status"),
                }
        if campaign.get("status") in {"funded", "pending_review", "active", "paused", "completed", "budget_exhausted"}:
            return {"ok": False, "error": "already_funded"}
        if not _campaign_status_allows_funding(campaign.get("status")):
            return {"ok": False, "error": "invalid_state"}

        required_cents = int(campaign.get("budget_cents") or 0)
        if required_cents <= 0:
            return {"ok": False, "error": "invalid_state"}

        cursor.execute(
            """
            INSERT INTO chain_wallets (
                profile_id, balance_cents, pending_balance_cents, lifetime_earned_cents,
                lifetime_spent_cents, withdrawable_balance_cents, status, created_at, updated_at
            )
            VALUES (%s, 0, 0, 0, 0, 0, 'active', now(), now())
            ON CONFLICT (profile_id) DO NOTHING
            """,
            (owner_profile_id,),
        )
        cursor.execute(
            """
            SELECT profile_id, COALESCE(balance_cents, 0) AS balance_cents, COALESCE(status, 'active') AS status
            FROM chain_wallets
            WHERE profile_id = %s
            FOR UPDATE
            """,
            (owner_profile_id,),
        )
        wallet = cursor.fetchone()
        if not wallet:
            return {"ok": False, "error": "payment_failed"}
        if str(wallet.get("status", "active")) == "locked":
            return {"ok": False, "error": "payment_failed"}
        if int(wallet.get("balance_cents") or 0) < required_cents:
            cursor.execute(
                """
                UPDATE chain_ad_campaigns
                SET status = 'pending_payment', updated_at = now()
                WHERE id = %s
                """,
                (campaign_id,),
            )
            return {"ok": False, "error": "insufficient_funds"}

        cursor.execute(
            """
            UPDATE chain_wallets
            SET balance_cents = balance_cents - %s,
                lifetime_spent_cents = COALESCE(lifetime_spent_cents, 0) + %s,
                updated_at = now()
            WHERE profile_id = %s AND balance_cents >= %s
            RETURNING balance_cents
            """,
            (required_cents, required_cents, owner_profile_id, required_cents),
        )
        balance_row = cursor.fetchone()
        if not balance_row:
            return {"ok": False, "error": "insufficient_funds"}

        wallet_tx_id = str(uuid.uuid4())
        payment_id = str(existing_payment["id"]) if existing_payment else str(uuid.uuid4())
        cursor.execute(
            """
            SELECT id
            FROM chain_wallets
            WHERE profile_id = %s
            LIMIT 1
            """,
            (owner_profile_id,),
        )
        wallet_id_row = cursor.fetchone()
        wallet_id = wallet_id_row["id"] if wallet_id_row else None
        cursor.execute(
            """
            INSERT INTO chain_wallet_transactions (
                id, wallet_id, profile_id, counterparty_profile_id, transaction_type, direction,
                amount_cents, fee_cents, net_amount_cents, currency, status, reference_type,
                reference_id, description, idempotency_key, metadata
            ) VALUES (%s, %s, %s, NULL, 'ad_campaign_funding', 'debit', %s, 0, %s, 'NAD', 'completed', 'ad_campaign', %s, %s, %s, %s::jsonb)
            ON CONFLICT (idempotency_key) DO NOTHING
            """,
            (
                wallet_tx_id,
                wallet_id,
                owner_profile_id,
                -required_cents,
                -required_cents,
                campaign_id,
                f"Funding campaign {campaign.get('title') or campaign_id}",
                funding_key,
                json.dumps({"campaign_id": str(campaign_id), "type": "advertising_funding"}),
            ),
        )
        cursor.execute(
            """
            SELECT id
            FROM chain_wallet_transactions
            WHERE idempotency_key = %s
            LIMIT 1
            """,
            (funding_key,),
        )
        tx_row = cursor.fetchone()
        wallet_tx_id = str(tx_row["id"]) if tx_row else wallet_tx_id

        amount_money = _cents_to_money(required_cents)
        cursor.execute(
            """
            INSERT INTO chain_ad_payments (
                id, campaign_id, profile_id, amount, amount_cents, currency, payment_method,
                status, description, wallet_transaction_id, idempotency_key, paid_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, 'NAD', 'wallet', 'completed', %s, %s, %s, now(), now())
            ON CONFLICT (idempotency_key) DO UPDATE SET
                wallet_transaction_id = EXCLUDED.wallet_transaction_id,
                status = 'completed',
                paid_at = COALESCE(chain_ad_payments.paid_at, EXCLUDED.paid_at)
            """,
            (
                payment_id,
                campaign_id,
                owner_profile_id,
                amount_money,
                required_cents,
                f"Wallet funding for campaign {campaign.get('title') or campaign_id}",
                wallet_tx_id,
                funding_key,
            ),
        )
        cursor.execute(
            """
            UPDATE chain_ad_campaigns
            SET status = 'funded',
                funded_at = COALESCE(funded_at, now()),
                funded_amount_cents = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (required_cents, campaign_id),
        )
        return {
            "ok": True,
            "payment_id": payment_id,
            "wallet_transaction_id": wallet_tx_id,
            "campaign_status": "funded",
            "amount_cents": required_cents,
        }

    try:
        return transaction_query(_callback, timeout_ms=5000)
    except Exception:
        return {"ok": False, "error": "payment_failed"}

# ── Approval Workflow ────────────────────────────────────────────────

def approve_campaign(campaign_id, admin_id=None, note=None):
    now = _utcnow()
    write_query(
        "UPDATE chain_ad_campaigns SET status = 'active', is_sponsored = TRUE, "
        "reviewed_by = %s, reviewed_at = %s, review_note = %s WHERE id = %s "
        "AND status IN ('pending_review', 'funded')",
        (admin_id, now, note, campaign_id)
    )
    return {"ok": True}

def reject_campaign(campaign_id, admin_id=None, note=None):
    now = _utcnow()
    write_query(
        "UPDATE chain_ad_campaigns SET status = 'rejected', reviewed_by = %s, "
        "reviewed_at = %s, review_note = %s WHERE id = %s",
        (admin_id, now, note, campaign_id)
    )
    return {"ok": True}

def pause_campaign(campaign_id, profile_id=None):
    if profile_id:
        write_query(
            "UPDATE chain_ad_campaigns SET status = 'paused' WHERE id = %s AND owner_id = %s",
            (campaign_id, profile_id)
        )
    else:
        write_query(
            "UPDATE chain_ad_campaigns SET status = 'paused' WHERE id = %s",
            (campaign_id,)
        )
    return {"ok": True}

def resume_campaign(campaign_id):
    write_query(
        "UPDATE chain_ad_campaigns SET status = 'active' WHERE id = %s AND status = 'paused'",
        (campaign_id,)
    )
    return {"ok": True}

def schedule_campaign(campaign_id, start_date, end_date=None):
    write_query(
        "UPDATE chain_ad_campaigns SET starts_at = %s, ends_at = %s, status = 'pending' WHERE id = %s",
        (start_date, end_date, campaign_id)
    )
    return {"ok": True}

# ── Creatives ────────────────────────────────────────────────────────

def create_creative(campaign_id, profile_id, creative_type="image",
                    media_url=None, headline=None, description=None,
                    cta_text="Learn More", destination_url=None,
                    thumbnail_url=None, sort_order=0, duration_seconds=0):
    cid = _uuid()
    try:
        write_query(
            """INSERT INTO chain_ad_creatives
               (id, campaign_id, profile_id, creative_type, media_url, headline,
                description, cta_text, destination_url, thumbnail_url,
                sort_order, duration_seconds)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (cid, campaign_id, profile_id, creative_type, media_url, headline,
             description, cta_text, destination_url, thumbnail_url,
             sort_order, duration_seconds)
        )
        return {"ok": True, "creative_id": cid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_creatives_for_campaign(campaign_id):
    return fast_query(
        "SELECT * FROM chain_ad_creatives WHERE campaign_id = %s AND is_active = TRUE ORDER BY sort_order",
        (campaign_id,), default=[]
    )

def update_creative(creative_id, **kwargs):
    allowed = {"creative_type","media_url","headline","description",
               "cta_text","destination_url","thumbnail_url","sort_order",
               "duration_seconds","is_active"}
    safe = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not safe:
        return {"ok": False, "error": "No valid fields"}
    sets = ", ".join(f'"{k}" = %s' for k in safe)
    write_query(f"UPDATE chain_ad_creatives SET {sets} WHERE id = %s", list(safe.values()) + [creative_id])
    return {"ok": True}

def delete_creative(creative_id, profile_id=None):
    if profile_id:
        rows = fast_query(
            """SELECT cr.id
               FROM chain_ad_creatives cr
               JOIN chain_ad_campaigns c ON cr.campaign_id = c.id
               WHERE cr.id = %s AND c.owner_id = %s AND c.is_deleted = FALSE
               LIMIT 1""",
            (creative_id, profile_id), default=[]
        )
        if not rows:
            return {"ok": False, "error": "Not found"}
    write_query("UPDATE chain_ad_creatives SET is_active = FALSE WHERE id = %s", (creative_id,))
    return {"ok": True}

# ── Placements ───────────────────────────────────────────────────────

def set_campaign_placements(campaign_id, placement_types):
    write_query("DELETE FROM chain_ad_placements WHERE campaign_id = %s", (campaign_id,))
    for pt in placement_types:
        pid = _uuid()
        write_query(
            "INSERT INTO chain_ad_placements (id, campaign_id, placement_type) VALUES (%s, %s, %s)",
            (pid, campaign_id, pt)
        )
    return {"ok": True}

def get_campaign_placements(campaign_id):
    return fast_query(
        "SELECT * FROM chain_ad_placements WHERE campaign_id = %s AND is_active = TRUE",
        (campaign_id,), default=[]
    )

# ── Targeting ────────────────────────────────────────────────────────

def set_campaign_targeting(campaign_id, targeting_data):
    existing = fast_query(
        "SELECT id FROM chain_ad_targeting WHERE campaign_id = %s", (campaign_id,), default=[]
    )
    safe = {
        "countries": targeting_data.get("countries", []),
        "regions": targeting_data.get("regions", []),
        "cities": targeting_data.get("cities", []),
        "languages": targeting_data.get("languages", []),
        "age_min": targeting_data.get("age_min", 13),
        "age_max": targeting_data.get("age_max", 100),
        "genders": targeting_data.get("genders", []),
        "interests": targeting_data.get("interests", []),
        "device_types": targeting_data.get("device_types", []),
        "targeting_verified": targeting_data.get("targeting_verified", False),
        "targeting_creators": targeting_data.get("targeting_creators", False),
        "targeting_businesses": targeting_data.get("targeting_businesses", False),
        "exclude_followers": targeting_data.get("exclude_followers", False),
        "custom_audience_ids": targeting_data.get("custom_audience_ids", []),
    }
    if existing:
        sets = ", ".join(f'"{k}" = %s' for k in safe)
        vals = list(safe.values()) + [campaign_id]
        write_query(f"UPDATE chain_ad_targeting SET {sets} WHERE campaign_id = %s", vals)
    else:
        tid = _uuid()
        cols = ", ".join(f'"{k}"' for k in safe)
        placeholders = ", ".join("%s" for _ in safe)
        vals = [tid, campaign_id] + list(safe.values())
        write_query(
            f"INSERT INTO chain_ad_targeting (id, campaign_id, {cols}) VALUES (%s, %s, {placeholders})",
            vals
        )
    return {"ok": True}

def get_campaign_targeting(campaign_id):
    rows = fast_query(
        "SELECT * FROM chain_ad_targeting WHERE campaign_id = %s", (campaign_id,), default=[]
    )
    return rows[0] if rows else None

# ── Ad Serving ───────────────────────────────────────────────────────

def get_active_campaigns(limit=20):
    now = _utcnow()
    return fast_query(
        """SELECT c.*, p.username, p.display_name, p.avatar_url
           FROM chain_ad_campaigns c JOIN chain_profiles p ON c.owner_id = p.id
           WHERE c.status = 'active' AND c.is_deleted = FALSE
             AND c.starts_at <= %s AND (c.ends_at IS NULL OR c.ends_at > %s)
           ORDER BY c.priority DESC, c.created_at DESC LIMIT %s""",
        (now, now, limit), timeout_ms=3000, default=[]
    )

def get_ads_for_placement(placement_type, viewer_id=None, slot_count=2, targeting_context=None):
    campaigns = get_active_campaigns(limit=slot_count * 5)
    matched = []
    for c in campaigns:
        placements = get_campaign_placements(c["id"])
        placement_types = [p["placement_type"] for p in placements]
        if placement_types and placement_type not in placement_types:
            continue
        if _is_ad_served(c["id"], viewer_id):
            continue
        if viewer_id and c.get("owner_id") == viewer_id:
            continue
        if targeting_context:
            if not _matches_targeting(c, targeting_context):
                continue
        _mark_ad_served(c["id"], viewer_id)
        creatives = get_creatives_for_campaign(c["id"])
        matched.append({
            "id": c["id"],
            "type": "ad",
            "ad_type": placement_type,
            "title": c.get("title", "Sponsored"),
            "objective": c.get("objective"),
            "media_type": c.get("media_type", "image"),
            "content_url": c.get("content_url", ""),
            "target_url": c.get("target_url", ""),
            "campaign_id": c["id"],
            "profile_id": c.get("owner_id"),
            "username": c.get("username"),
            "display_name": c.get("display_name"),
            "avatar_url": c.get("avatar_url"),
            "is_ad": True,
            "sponsored": True,
            "creatives": creatives,
            "bid_type": c.get("bid_type", "auto"),
        })
        if len(matched) >= slot_count:
            break
    for ad in matched:
        record_impression(ad["campaign_id"], viewer_id)
    return matched

def get_ads_for_feed(viewer_id=None, slot_count=2):
    return get_ads_for_placement("feed", viewer_id, slot_count)

def get_ads_for_reels(viewer_id=None, slot_count=1):
    return get_ads_for_placement("reels", viewer_id, slot_count)

def get_ads_for_stories(viewer_id=None, slot_count=1):
    return get_ads_for_placement("stories", viewer_id, slot_count)

def get_ads_for_search(viewer_id=None, slot_count=2):
    return get_ads_for_placement("search", viewer_id, slot_count)

def get_ads_for_marketplace(viewer_id=None, slot_count=2):
    return get_ads_for_placement("marketplace", viewer_id, slot_count)

def get_ads_for_discover(viewer_id=None, slot_count=2):
    return get_ads_for_placement("discover", viewer_id, slot_count)

def get_ads_for_dating(viewer_id=None, slot_count=1):
    return get_ads_for_placement("dating", viewer_id, slot_count)

def get_ads_for_live(viewer_id=None, slot_count=1):
    return get_ads_for_placement("live", viewer_id, slot_count)

def get_ads_for_notifications(viewer_id=None, slot_count=1):
    return get_ads_for_placement("notifications", viewer_id, slot_count)

def _matches_targeting(campaign, context):
    targeting = get_campaign_targeting(campaign["id"])
    if not targeting:
        return True
    if targeting.get("countries") and context.get("country"):
        if context["country"] not in targeting["countries"]:
            return False
    if targeting.get("age_min") and context.get("age"):
        if context["age"] < targeting["age_min"]:
            return False
    if targeting.get("age_max") and context.get("age"):
        if context["age"] > targeting["age_max"]:
            return False
    if targeting.get("genders") and context.get("gender"):
        if context["gender"] not in targeting["genders"]:
            return False
    if targeting.get("device_types") and context.get("device_type"):
        if context["device_type"] not in targeting["device_types"]:
            return False
    if targeting.get("targeting_verified") and not context.get("is_verified"):
        return False
    if targeting.get("targeting_creators") and not context.get("is_creator"):
        return False
    if targeting.get("targeting_businesses") and not context.get("is_business"):
        return False
    return True

# ── Impressions & Clicks ─────────────────────────────────────────────

def _chargeable_campaign(cursor, campaign_id):
    cursor.execute(
        """
        SELECT *
        FROM chain_ad_campaigns
        WHERE id = %s AND is_deleted = FALSE
        FOR UPDATE
        """,
        (campaign_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return _normalize_campaign_money_fields(dict(row))

def _campaign_within_schedule(campaign, now=None):
    now = now or _utcnow()
    starts_at = campaign.get("starts_at")
    ends_at = campaign.get("ends_at")
    if starts_at and starts_at > now:
        return False
    if ends_at and ends_at <= now:
        return False
    return True

def _mark_campaign_budget_exhausted(cursor, campaign_id):
    cursor.execute(
        """
        UPDATE chain_ad_campaigns
        SET status = 'budget_exhausted', updated_at = now()
        WHERE id = %s
        """,
        (campaign_id,),
    )

def _remaining_budget_cents(campaign):
    return max(int(campaign.get("funded_amount_cents", 0)) - int(campaign.get("spent_amount_cents", 0)), 0)

def _click_charge_cents(campaign):
    return max(int(campaign.get("bid_amount_cents") or 0), 0)

def _daily_remaining_cents(campaign):
    limit_cents = int(campaign.get("daily_budget_cents") or 0)
    if limit_cents <= 0:
        return None
    return max(limit_cents - int(campaign.get("daily_spend_cents") or 0), 0)

def record_impression(campaign_id, profile_id=None):
    try:
        def _callback(cursor):
            campaign = _chargeable_campaign(cursor, campaign_id)
            if not campaign:
                return {"ok": False, "error": "campaign_not_found"}
            if not _campaign_status_is_chargeable(campaign.get("status")):
                return {"ok": False, "error": "invalid_state"}
            if not _campaign_within_schedule(campaign):
                return {"ok": False, "error": "invalid_state"}
            if _remaining_budget_cents(campaign) <= 0:
                _mark_campaign_budget_exhausted(cursor, campaign_id)
                return {"ok": False, "error": "budget_exhausted"}
            cursor.execute(
                "INSERT INTO chain_ad_impressions (campaign_id, profile_id) VALUES (%s, %s)",
                (campaign_id, profile_id),
            )
            cursor.execute(
                "UPDATE chain_ad_campaigns SET impressions_count = COALESCE(impressions_count, 0) + 1 WHERE id = %s",
                (campaign_id,),
            )
            return {"ok": True}
        result = transaction_query(_callback, timeout_ms=3000)
        if result.get("ok"):
            _update_daily_analytics(campaign_id, profile_id, impressions=1)
            return True
        return False
    except Exception:
        return False

def rollback_click(campaign_id, click_id, charge_cents=0, cursor=None):
    charge_cents = max(int(charge_cents or 0), 0)
    if cursor is not None:
        cursor.execute(
            "DELETE FROM chain_ad_clicks WHERE id = %s AND campaign_id = %s",
            (click_id, campaign_id),
        )
        cursor.execute(
            """
            UPDATE chain_ad_campaigns
            SET clicks_count = GREATEST(COALESCE(clicks_count, 0) - 1, 0),
                spent_amount_cents = GREATEST(COALESCE(spent_amount_cents, 0) - %s, 0),
                spent_amount = GREATEST(COALESCE(spent_amount, 0) - %s, 0),
                daily_spend_cents = GREATEST(COALESCE(daily_spend_cents, 0) - %s, 0),
                status = CASE
                    WHEN status = 'budget_exhausted' AND GREATEST(COALESCE(funded_amount_cents, 0) - GREATEST(COALESCE(spent_amount_cents, 0) - %s, 0), 0) > 0
                    THEN 'active'
                    ELSE status
                END,
                updated_at = now()
            WHERE id = %s
            """,
            (
                charge_cents,
                _cents_to_money(charge_cents),
                charge_cents,
                charge_cents,
                campaign_id,
            ),
        )
        return True
    try:
        def _callback(tx_cursor):
            return rollback_click(campaign_id, click_id, charge_cents=charge_cents, cursor=tx_cursor)
        return bool(transaction_query(_callback, timeout_ms=3000))
    except Exception:
        return False

def _run_fraud_checks(cursor, campaign_id, profile_id, ip_address=None, user_agent=None, click_id=None):
    fraud_score = 0
    fraud_flags = []
    if ip_address:
        cursor.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM chain_ad_clicks c
            JOIN chain_ad_fraud_events f ON c.id::text = f.details->>'click_id'
            WHERE f.ip_address = %s AND f.detected_at > %s
            """,
            (ip_address, _utcnow() - timedelta(hours=1)),
        )
        recent = cursor.fetchone() or {"cnt": 0}
        if int(recent.get("cnt") or 0) > 50:
            fraud_flags.append({"type": "bot_traffic", "detail": f"High click rate from IP: {ip_address}"})
            fraud_score += 30
    if user_agent:
        known_bots = ["bot", "crawler", "spider", "scrapy", "curl", "python-requests", "go-http-client"]
        ua_lower = user_agent.lower()
        for bot in known_bots:
            if bot in ua_lower:
                fraud_flags.append({"type": "automated_click", "detail": f"Bot UA: {user_agent[:100]}"})
                fraud_score += 40
                break
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM chain_ad_clicks
        WHERE campaign_id = %s AND profile_id = %s AND clicked_at > %s
        """,
        (campaign_id, profile_id, _utcnow() - timedelta(seconds=5)),
    )
    duplicate = cursor.fetchone() or {"cnt": 0}
    if int(duplicate.get("cnt") or 0) > 3:
        fraud_flags.append({"type": "duplicate_click", "detail": "More than 3 clicks in 5s"})
        fraud_score += 25
    if fraud_score > 0:
        details = {"click_id": str(click_id) if click_id else None, "flags": fraud_flags}
        cursor.execute(
            """
            INSERT INTO chain_ad_fraud_events
            (id, campaign_id, profile_id, fraud_type, score, ip_address, user_agent, details)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (_uuid(), campaign_id, profile_id, fraud_flags[0]["type"], fraud_score, ip_address, user_agent, json.dumps(details)),
        )
    return {"fraud_score": fraud_score, "fraud_flags": fraud_flags, "is_fraud": fraud_score >= 50}

def record_click(campaign_id, profile_id=None, client_event_id=None):
    try:
        def _callback(cursor):
            campaign = _chargeable_campaign(cursor, campaign_id)
            if not campaign:
                return {"ok": False, "error": "campaign_not_found"}
            if not _campaign_status_is_chargeable(campaign.get("status")):
                return {"ok": False, "error": "invalid_state"}
            if not _campaign_within_schedule(campaign):
                return {"ok": False, "error": "invalid_state"}
            remaining = _remaining_budget_cents(campaign)
            if remaining <= 0:
                _mark_campaign_budget_exhausted(cursor, campaign_id)
                return {"ok": False, "error": "budget_exhausted"}
            if client_event_id:
                cursor.execute(
                    """
                    SELECT id
                    FROM chain_ad_clicks
                    WHERE campaign_id = %s AND profile_id IS NOT DISTINCT FROM %s AND client_event_id = %s
                    LIMIT 1
                    """,
                    (campaign_id, profile_id, client_event_id),
                )
                existing = cursor.fetchone()
                if existing:
                    return {"ok": True, "click_id": str(existing["id"]), "idempotent": True}
            charge_cents = _click_charge_cents(campaign)
            daily_remaining = _daily_remaining_cents(campaign)
            if charge_cents > remaining:
                _mark_campaign_budget_exhausted(cursor, campaign_id)
                return {"ok": False, "error": "budget_exhausted"}
            if daily_remaining is not None and charge_cents > daily_remaining:
                return {"ok": False, "error": "daily_budget_reached"}
            cursor.execute(
                """
                INSERT INTO chain_ad_clicks (campaign_id, profile_id, client_event_id)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (campaign_id, profile_id, client_event_id),
            )
            click_row = cursor.fetchone()
            spent_amount_cents = int(campaign.get("spent_amount_cents") or 0) + charge_cents
            daily_spend_cents = int(campaign.get("daily_spend_cents") or 0) + charge_cents
            next_status = "budget_exhausted" if spent_amount_cents >= int(campaign.get("funded_amount_cents") or 0) else campaign.get("status")
            cursor.execute(
                """
                UPDATE chain_ad_campaigns
                SET clicks_count = COALESCE(clicks_count, 0) + 1,
                    spent_amount_cents = %s,
                    spent_amount = %s,
                    daily_spend_cents = %s,
                    status = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (spent_amount_cents, _cents_to_money(spent_amount_cents), daily_spend_cents, next_status, campaign_id),
            )
            return {"ok": True, "click_id": str(click_row["id"]), "charge_cents": charge_cents, "idempotent": False}
        result = transaction_query(_callback, timeout_ms=3000)
        if result.get("ok") and not result.get("idempotent"):
            _update_daily_analytics(campaign_id, profile_id, clicks=1, spend=float(_cents_to_money(result.get("charge_cents", 0))))
        return result
    except Exception:
        return {"ok": False, "error": "click_record_failed"}

def _update_daily_analytics(campaign_id, profile_id=None, impressions=0, clicks=0,
                            spend=0, video_views=0, conversions=0):
    today = _today()
    try:
        if impressions:
            write_query(
                """INSERT INTO chain_ad_analytics (id, campaign_id, profile_id, date, impressions, clicks, spend)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)
                   ON CONFLICT (campaign_id, date) DO UPDATE SET
                   impressions = chain_ad_analytics.impressions + %s,
                   clicks = chain_ad_analytics.clicks + %s,
                   spend = chain_ad_analytics.spend + %s""",
                (_uuid(), campaign_id, profile_id, today, impressions, clicks, spend,
                 impressions, clicks, spend)
            )
    except Exception:
        pass

# ── Analytics ────────────────────────────────────────────────────────

def get_campaign_stats(campaign_id):
    rows = fast_query(
        """SELECT COALESCE(SUM(impressions),0) as impressions,
                  COALESCE(SUM(clicks),0) as clicks,
                  COALESCE(SUM(spend),0) as spend,
                  COALESCE(SUM(video_views),0) as video_views,
                  COALESCE(SUM(conversions),0) as conversions,
                  COALESCE(SUM(website_visits),0) as website_visits,
                  COALESCE(SUM(profile_visits),0) as profile_visits
           FROM chain_ad_analytics WHERE campaign_id = %s""",
        (campaign_id,), default=[{"impressions":0,"clicks":0,"spend":0,"video_views":0,
                                   "conversions":0,"website_visits":0,"profile_visits":0}]
    )
    stats = rows[0]
    total_impressions = stats["impressions"]
    total_clicks = stats["clicks"]
    stats["ctr"] = round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0
    stats["cpc"] = round((stats["spend"] / total_clicks), 4) if total_clicks > 0 else 0
    stats["cpm"] = round((stats["spend"] / total_impressions * 1000), 4) if total_impressions > 0 else 0
    return stats

def get_campaign_daily_stats(campaign_id, days=30):
    return fast_query(
        "SELECT * FROM chain_ad_analytics WHERE campaign_id = %s ORDER BY date DESC LIMIT %s",
        (campaign_id, days), default=[]
    )

def get_advertiser_stats(profile_id):
    campaigns = get_campaigns_for_user(profile_id)
    total_spend = 0
    total_impressions = 0
    total_clicks = 0
    for c in campaigns:
        total_spend += c.get("spent_amount", 0) or 0
        total_impressions += c.get("impressions_count", 0) or 0
        total_clicks += c.get("clicks_count", 0) or 0
    return {
        "campaigns_count": len(campaigns),
        "total_spend": total_spend,
        "total_impressions": total_impressions,
        "total_clicks": total_clicks,
        "ctr": round((total_clicks / total_impressions * 100), 2) if total_impressions > 0 else 0,
    }

def get_admin_dashboard_stats():
    rows = fast_query(
        """SELECT
            COUNT(*) FILTER (WHERE status = 'active') as active_campaigns,
            COUNT(*) FILTER (WHERE status = 'pending') as pending_approval,
            COUNT(*) FILTER (WHERE status = 'paused') as paused_campaigns,
            COUNT(*) FILTER (WHERE status = 'rejected') as rejected_campaigns,
            COALESCE(SUM(spent_amount), 0) as total_revenue
         FROM chain_ad_campaigns WHERE is_deleted = FALSE""",
        (), default=[{}]
    )[0]

    today_rows = fast_query(
        "SELECT COALESCE(SUM(spend), 0) as today_revenue FROM chain_ad_analytics WHERE date = %s",
        (_today(),), default=[{"today_revenue": 0}]
    )
    rows["today_revenue"] = today_rows[0]["today_revenue"] if today_rows else 0

    month_start = _today().replace(day=1)
    month_rows = fast_query(
        "SELECT COALESCE(SUM(spend), 0) as month_revenue FROM chain_ad_analytics WHERE date >= %s",
        (month_start,), default=[{"month_revenue": 0}]
    )
    rows["month_revenue"] = month_rows[0]["month_revenue"] if month_rows else 0

    ctr_rows = fast_query(
        """SELECT COALESCE(SUM(impressions),0) as total_imp, COALESCE(SUM(clicks),0) as total_clicks
           FROM chain_ad_analytics""",
        (), default=[{"total_imp":0,"total_clicks":0}]
    )
    total_imp = ctr_rows[0]["total_imp"] if ctr_rows else 0
    total_clicks = ctr_rows[0]["total_clicks"] if ctr_rows else 0
    rows["ctr"] = round((total_clicks / total_imp * 100), 2) if total_imp > 0 else 0

    conv_rows = fast_query(
        "SELECT COALESCE(SUM(conversions),0) as total_conv FROM chain_ad_analytics",
        (), default=[{"total_conv": 0}]
    )
    rows["conversions"] = conv_rows[0]["total_conv"] if conv_rows else 0

    return rows

def get_top_advertisers(limit=10):
    return fast_query(
        """SELECT c.owner_id, p.username, p.display_name, p.avatar_url,
                  SUM(c.spent_amount) as total_spend,
                  COUNT(c.id) as campaign_count
           FROM chain_ad_campaigns c JOIN chain_profiles p ON c.owner_id = p.id
           WHERE c.is_deleted = FALSE
           GROUP BY c.owner_id, p.username, p.display_name, p.avatar_url
           ORDER BY total_spend DESC LIMIT %s""",
        (limit,), default=[]
    )

def get_top_performing_ads(limit=10):
    return fast_query(
        """SELECT c.*, p.username, p.display_name,
                  COALESCE(a.impressions,0) as impressions,
                  COALESCE(a.clicks,0) as clicks,
                  CASE WHEN COALESCE(a.impressions,0) > 0
                       THEN ROUND(a.clicks::DECIMAL / a.impressions * 100, 2)
                       ELSE 0 END as ctr
           FROM chain_ad_campaigns c
           JOIN chain_profiles p ON c.owner_id = p.id
           LEFT JOIN (
               SELECT campaign_id, SUM(impressions) as impressions, SUM(clicks) as clicks
               FROM chain_ad_analytics GROUP BY campaign_id
           ) a ON c.id = a.campaign_id
           WHERE c.status = 'active' AND c.is_deleted = FALSE
           ORDER BY a.impressions DESC NULLS LAST LIMIT %s""",
        (limit,), default=[]
    )

# ── Payments / Billing ──────────────────────────────────────────────

def create_payment(campaign_id, profile_id, amount, method="wallet",
                   currency="NAD", description=None, idempotency_key=None):
    campaign = get_campaign(campaign_id)
    if not campaign or campaign.get("owner_id") != profile_id:
        return {"ok": False, "error": "campaign_not_found"}
    if method != "wallet" or currency != "NAD":
        return {"ok": False, "error": "payment_failed"}
    return fund_campaign(campaign_id, profile_id, idempotency_key=idempotency_key)

def get_payments_for_profile(profile_id, limit=50):
    return fast_query(
        "SELECT * FROM chain_ad_payments WHERE profile_id = %s ORDER BY created_at DESC LIMIT %s",
        (profile_id, limit), default=[]
    )

def get_payments_for_admin(limit=100):
    return fast_query(
        "SELECT p.*, pr.username, pr.display_name FROM chain_ad_payments p "
        "JOIN chain_profiles pr ON p.profile_id = pr.id "
        "ORDER BY p.created_at DESC LIMIT %s",
        (limit,), default=[]
    )

# ── Coupons ──────────────────────────────────────────────────────────

def create_coupon(code, discount_type, discount_value, description=None,
                  min_spend=0, max_discount=None, usage_limit=1,
                  expires_at=None):
    cid = _uuid()
    try:
        write_query(
            """INSERT INTO chain_ad_coupons
               (id, code, description, discount_type, discount_value, min_spend,
                max_discount, usage_limit, expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (cid, code.upper(), description, discount_type, discount_value,
             min_spend, max_discount, usage_limit, expires_at)
        )
        return {"ok": True, "coupon_id": cid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def validate_coupon(code, profile_id=None):
    rows = fast_query(
        "SELECT * FROM chain_ad_coupons WHERE code = %s AND is_active = TRUE "
        "AND (expires_at IS NULL OR expires_at > %s) "
        "AND (usage_limit IS NULL OR used_count < usage_limit)",
        (code.upper(), _utcnow()), default=[]
    )
    if not rows:
        return {"ok": False, "error": "Invalid or expired coupon"}
    coupon = rows[0]
    if coupon.get("profile_id") and coupon["profile_id"] != profile_id:
        return {"ok": False, "error": "Coupon not valid for this account"}
    return {"ok": True, "coupon": coupon}

def apply_coupon(code, amount):
    result = validate_coupon(code)
    if not result["ok"]:
        return result
    coupon = result["coupon"]
    if coupon["discount_type"] == "percentage":
        discount = amount * (coupon["discount_value"] / 100)
        if coupon.get("max_discount"):
            discount = min(discount, coupon["max_discount"])
    else:
        discount = min(coupon["discount_value"], amount)
    if amount - discount < coupon.get("min_spend", 0):
        return {"ok": False, "error": "Amount below minimum spend"}
    write_query(
        "UPDATE chain_ad_coupons SET used_count = used_count + 1 WHERE id = %s",
        (coupon["id"],)
    )
    return {"ok": True, "discount": discount, "final_amount": amount - discount}

def get_coupons(limit=50):
    return fast_query("SELECT * FROM chain_ad_coupons ORDER BY created_at DESC LIMIT %s", (limit,), default=[])

# ── Promotions ───────────────────────────────────────────────────────

def create_promotion(campaign_id, content_type, content_id, profile_id):
    pid = _uuid()
    try:
        write_query(
            "INSERT INTO chain_ad_promotions (id, campaign_id, content_type, content_id, profile_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            (pid, campaign_id, content_type, content_id, profile_id)
        )
        return {"ok": True, "promotion_id": pid}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_promotions_for_content(content_type, content_id):
    return fast_query(
        "SELECT p.*, c.title as campaign_title, c.owner_id "
        "FROM chain_ad_promotions p JOIN chain_ad_campaigns c ON p.campaign_id = c.id "
        "WHERE p.content_type = %s AND p.content_id = %s AND p.is_active = TRUE AND c.status = 'active'",
        (content_type, content_id), default=[]
    )

# ── Moderation & AI Review ───────────────────────────────────────────

def submit_for_review(campaign_id):
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"ok": False, "error": "Campaign not found"}
    if campaign.get("status") == "pending_review":
        return {"ok": True, "status": "pending_review"}
    if campaign.get("status") != "funded":
        return {"ok": False, "error": "invalid_state"}
    write_query("UPDATE chain_ad_campaigns SET status = 'pending_review' WHERE id = %s", (campaign_id,))
    existing = fast_query(
        "SELECT id FROM chain_ad_moderation WHERE campaign_id = %s", (campaign_id,), default=[]
    )
    if not existing:
        mid = _uuid()
        write_query(
            "INSERT INTO chain_ad_moderation (id, campaign_id) VALUES (%s, %s)",
            (mid, campaign_id)
        )
    return {"ok": True}

def run_ai_review(campaign_id):
    campaign = get_campaign(campaign_id)
    if not campaign:
        return {"ok": False, "error": "Campaign not found"}
    flags = []
    score = 100.0
    content_url = campaign.get("content_url", "") or ""
    title = campaign.get("title", "") or ""
    objective = campaign.get("objective", "") or ""
    text = f"{title} {objective}".lower()
    spam_keywords = ["free money", "click here", "act now", "limited time",
                     "buy now", "congratulations", "you won", "prize"]
    for kw in spam_keywords:
        if kw in text:
            flags.append({"type": "spam_keyword", "keyword": kw})
            score -= 15
    misleading_patterns = ["guaranteed", "instant", "miracle", "cure",
                           "secret", "hidden", "exclusive access"]
    for pat in misleading_patterns:
        if pat in text:
            flags.append({"type": "misleading", "pattern": pat})
            score -= 10
    prohibited = ["casino", "gambling", "crypto", "weapon", "drug",
                  "alcohol", "tobacco", "adult", "escort", "xxx"]
    for p in prohibited:
        if p in text:
            flags.append({"type": "prohibited_product", "product": p})
            score -= 25
    if "http" in content_url.lower():
        score -= 5
        flags.append({"type": "external_link"})
    score = max(0, min(100, score))
    is_flagged = score < 60 or any(f["type"] == "prohibited_product" for f in flags)
    recommendation = "auto_approve" if score >= 70 else "manual_review" if score >= 40 else "reject"
    write_query(
        """UPDATE chain_ad_moderation SET
           ai_score = %s, ai_flagged = %s, ai_flags = %s::jsonb,
           ai_recommendation = %s, review_status = 'ai_reviewed', updated_at = now()
           WHERE campaign_id = %s""",
        (score, is_flagged, json.dumps(flags), recommendation, campaign_id)
    )
    write_query(
        "UPDATE chain_ad_campaigns SET ai_score = %s, ai_flagged = %s, ai_flags = %s::jsonb WHERE id = %s",
        (score, is_flagged, json.dumps(flags), campaign_id)
    )
    return {
        "ok": True,
        "score": score,
        "flagged": is_flagged,
        "flags": flags,
        "recommendation": recommendation,
    }

def get_moderation_queue(status="pending", limit=50):
    return fast_query(
        """SELECT m.*, c.title, c.owner_id, c.status as campaign_status,
                  c.content_url, c.objective, c.budget,
                  p.username, p.display_name, p.avatar_url
           FROM chain_ad_moderation m
           JOIN chain_ad_campaigns c ON m.campaign_id = c.id
           JOIN chain_profiles p ON c.owner_id = p.id
           WHERE m.review_status = %s
           ORDER BY m.created_at ASC LIMIT %s""",
        (status, limit), default=[]
    )

def get_all_moderation(limit=100):
    return fast_query(
        """SELECT m.*, c.title, c.owner_id, c.status as campaign_status,
                  p.username, p.display_name
           FROM chain_ad_moderation m
           JOIN chain_ad_campaigns c ON m.campaign_id = c.id
           JOIN chain_profiles p ON c.owner_id = p.id
           ORDER BY m.created_at DESC LIMIT %s""",
        (limit,), default=[]
    )

def review_moderation(moderation_id, review_status, reviewer_id, notes=None):
    write_query(
        "UPDATE chain_ad_moderation SET review_status = %s, reviewed_by = %s, "
        "reviewed_at = now(), notes = %s, updated_at = now() WHERE id = %s",
        (review_status, reviewer_id, notes, moderation_id)
    )
    return {"ok": True}

# ── Fraud Detection ─────────────────────────────────────────────────

def check_fraud(campaign_id, profile_id, ip_address=None, user_agent=None, click_id=None):
    fraud_score = 0
    fraud_flags = []
    if ip_address:
        recent = fast_query(
            "SELECT COUNT(*) as cnt FROM chain_ad_clicks c JOIN chain_ad_fraud_events f "
            "ON c.id::text = f.details->>'click_id' "
            "WHERE f.ip_address = %s AND f.detected_at > %s",
            (ip_address, _utcnow() - timedelta(hours=1)), default=[{"cnt": 0}]
        )
        if recent and recent[0]["cnt"] > 50:
            fraud_flags.append({"type": "bot_traffic", "detail": f"High click rate from IP: {ip_address}"})
            fraud_score += 30
    if user_agent:
        known_bots = ["bot", "crawler", "spider", "scrapy", "curl", "python-requests", "go-http-client"]
        ua_lower = user_agent.lower()
        for bot in known_bots:
            if bot in ua_lower:
                fraud_flags.append({"type": "automated_click", "detail": f"Bot UA: {user_agent[:100]}"})
                fraud_score += 40
                break
    duplicate = fast_query(
        "SELECT COUNT(*) as cnt FROM chain_ad_clicks "
        "WHERE campaign_id = %s AND profile_id = %s AND clicked_at > %s",
        (campaign_id, profile_id, _utcnow() - timedelta(seconds=5)), default=[{"cnt": 0}]
    )
    if duplicate and duplicate[0]["cnt"] > 3:
        fraud_flags.append({"type": "duplicate_click", "detail": f"More than 3 clicks in 5s"})
        fraud_score += 25
    if fraud_score > 0:
        eid = _uuid()
        details = {
            "click_id": str(click_id) if click_id else None,
            "flags": fraud_flags,
        }
        write_query(
            """INSERT INTO chain_ad_fraud_events
               (id, campaign_id, profile_id, fraud_type, score, ip_address, user_agent, details)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)""",
            (eid, campaign_id, profile_id, fraud_flags[0]["type"],
             fraud_score, ip_address, user_agent, json.dumps(details))
        )
    return {"fraud_score": fraud_score, "fraud_flags": fraud_flags, "is_fraud": fraud_score >= 50}

def track_click(campaign_id, profile_id=None, ip_address=None, user_agent=None):
    try:
        def _callback(cursor):
            campaign = _chargeable_campaign(cursor, campaign_id)
            if not campaign:
                return {"ok": False, "error": "campaign_not_found", "is_fraud": False}
            if not _campaign_status_is_chargeable(campaign.get("status")):
                return {"ok": False, "error": "invalid_state", "is_fraud": False}
            if not _campaign_within_schedule(campaign):
                return {"ok": False, "error": "invalid_state", "is_fraud": False}

            remaining = _remaining_budget_cents(campaign)
            if remaining <= 0:
                _mark_campaign_budget_exhausted(cursor, campaign_id)
                return {"ok": False, "error": "budget_exhausted", "is_fraud": False}

            charge_cents = _click_charge_cents(campaign)
            if charge_cents <= 0:
                return {"ok": False, "error": "invalid_state", "is_fraud": False}
            if charge_cents > remaining:
                _mark_campaign_budget_exhausted(cursor, campaign_id)
                return {"ok": False, "error": "budget_exhausted", "is_fraud": False}

            daily_remaining = _daily_remaining_cents(campaign)
            if daily_remaining is not None and charge_cents > daily_remaining:
                return {"ok": False, "error": "daily_budget_reached", "is_fraud": False}

            cursor.execute(
                """
                INSERT INTO chain_ad_clicks (campaign_id, profile_id)
                VALUES (%s, %s)
                RETURNING id
                """,
                (campaign_id, profile_id),
            )
            click_row = cursor.fetchone()
            click_id = str(click_row["id"])
            spent_amount_cents = int(campaign.get("spent_amount_cents") or 0) + charge_cents
            daily_spend_cents = int(campaign.get("daily_spend_cents") or 0) + charge_cents
            next_status = "budget_exhausted" if spent_amount_cents >= int(campaign.get("funded_amount_cents") or 0) else campaign.get("status")
            cursor.execute(
                """
                UPDATE chain_ad_campaigns
                SET clicks_count = COALESCE(clicks_count, 0) + 1,
                    spent_amount_cents = %s,
                    spent_amount = %s,
                    daily_spend_cents = %s,
                    status = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (spent_amount_cents, _cents_to_money(spent_amount_cents), daily_spend_cents, next_status, campaign_id),
            )

            fraud = _run_fraud_checks(
                cursor,
                campaign_id,
                profile_id,
                ip_address=ip_address,
                user_agent=user_agent,
                click_id=click_id,
            )
            if fraud.get("is_fraud"):
                rollback_click(campaign_id, click_id, charge_cents=charge_cents, cursor=cursor)
                return {
                    "ok": False,
                    "error": "Click blocked by fraud detection",
                    "is_fraud": True,
                    "fraud": fraud,
                }
            return {
                "ok": True,
                "click_id": click_id,
                "is_fraud": False,
                "fraud": fraud,
                "charge_cents": charge_cents,
            }

        result = transaction_query(_callback, timeout_ms=5000)
        if result.get("ok"):
            _update_daily_analytics(
                campaign_id,
                profile_id,
                clicks=1,
                spend=float(_cents_to_money(result.get("charge_cents", 0))),
            )
        return result
    except Exception:
        return {"ok": False, "error": "click_record_failed", "is_fraud": False}

def get_fraud_events(campaign_id=None, limit=50):
    if campaign_id:
        rows = fast_query(
            "SELECT * FROM chain_ad_fraud_events WHERE campaign_id = %s ORDER BY detected_at DESC LIMIT %s",
            (campaign_id, limit), default=[]
        )
    else:
        rows = fast_query(
        "SELECT * FROM chain_ad_fraud_events ORDER BY detected_at DESC LIMIT %s",
        (limit,), default=[]
        )
    for row in rows:
        normalized = normalize_fraud_event_details(row.get("details"))
        row["details"] = normalized
        row["click_id"] = normalized["click_id"]
        row["flags"] = normalized["flags"]
    return rows

# ── Campaign Status Auto-Expiry ──────────────────────────────────────

def expire_past_campaigns():
    now = _utcnow()
    write_query(
        "UPDATE chain_ad_campaigns SET status = 'expired' WHERE status = 'active' "
        "AND ends_at IS NOT NULL AND ends_at < %s",
        (now,)
    )
