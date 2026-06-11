from datetime import datetime, timezone

from services.admin_auth_service import log_admin_action
from services.profile_service import get_profile_by_id
from services.supabase_safe import safe_insert, safe_select, safe_update
from services.wallet_action_service import get_or_create_wallet, record_wallet_transaction

COIN_VALUE_NAD = 5
PLATFORM_FEE_RATE = 0.10


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _safe_int(value, default=0):
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def create_album(profile_id, title, description, genre, cover_url, price_coins, cover_upload_id=None):
    payload = {
        "profile_id": profile_id,
        "title": title,
        "description": description,
        "genre": genre,
        "album_cover_url": cover_url,
        "cover_upload_id": cover_upload_id,
        "price_coins": _safe_int(price_coins, 0),
        "approval_status": "pending",
        "is_public": False,
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_music_albums", payload)
    return inserted[0] if inserted else payload


def create_track(profile_id, album_id, title, audio_url, price_coins, audio_upload_id=None):
    coins = _safe_int(price_coins, 0)
    payload = {
        "album_id": album_id,
        "profile_id": profile_id,
        "title": title,
        "audio_url": audio_url,
        "audio_upload_id": audio_upload_id,
        "price_coins": coins,
        "price_nad": coins * COIN_VALUE_NAD,
        "approval_status": "pending",
        "is_public": False,
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_music_tracks", payload)
    return inserted[0] if inserted else payload


def create_marketplace_item(profile_id, item_type, title, description, media_url, cover_url, price_coins, premium_locked, media_upload_id=None, cover_upload_id=None, media_metadata=None, cover_metadata=None):
    coins = _safe_int(price_coins, 0)
    payload = {
        "profile_id": profile_id,
        "item_type": item_type,
        "title": title,
        "description": description,
        "media_url": media_url,
        "cover_url": cover_url,
        "media_bucket": (media_metadata or {}).get("bucket"),
        "media_path": (media_metadata or {}).get("path"),
        "mime_type": (media_metadata or {}).get("mime_type"),
        "size_bytes": (media_metadata or {}).get("size_bytes"),
        "cover_bucket": (cover_metadata or {}).get("bucket"),
        "cover_path": (cover_metadata or {}).get("path"),
        "cover_mime_type": (cover_metadata or {}).get("mime_type"),
        "cover_size_bytes": (cover_metadata or {}).get("size_bytes"),
        "media_upload_id": media_upload_id,
        "cover_upload_id": cover_upload_id,
        "price_coins": coins,
        "price_nad": coins * COIN_VALUE_NAD,
        "is_premium_locked": bool(premium_locked),
        "approval_status": "pending",
        "moderation_status": "pending",
        "is_public": False,
        "download_enabled": False,
        "created_at": _utcnow_iso(),
        "updated_at": _utcnow_iso(),
    }
    inserted = safe_insert("chain_marketplace_items", payload)
    return inserted[0] if inserted else payload


def list_my_items(profile_id):
    return safe_select("chain_marketplace_items", filters={"profile_id": profile_id}, limit=50)


def list_public_items():
    items = safe_select("chain_marketplace_items", filters={"is_public": True}, limit=50)
    approved = [item for item in items if (item.get("approval_status") == "approved" or item.get("moderation_status") == "approved")]
    return sorted(approved, key=lambda item: (not bool(item.get("is_featured")), item.get("created_at") or ""), reverse=False)


def get_item(item_id):
    rows = safe_select("chain_marketplace_items", filters={"id": item_id}, limit=1, order_by=None)
    return rows[0] if rows else None


def user_has_purchased_item(profile_id, item_id):
    if not profile_id:
        return False
    rows = safe_select("chain_media_purchases", filters={"buyer_profile_id": profile_id, "item_id": item_id}, limit=1, order_by=None)
    return bool(rows and rows[0].get("purchase_status", rows[0].get("status")) == "completed")


def get_item_access(profile_id, item_id):
    item = get_item(item_id)
    if not item:
        return {"item": None, "can_download": False, "is_locked": True, "has_purchased": False, "show_blur": False}
    profile = get_profile_by_id(profile_id) if profile_id else None
    purchase_rows = safe_select("chain_media_purchases", filters={"buyer_profile_id": profile_id, "item_id": item_id}, limit=1, order_by=None) if profile_id else []
    purchase = purchase_rows[0] if purchase_rows else None
    has_purchased = bool(purchase and purchase.get("purchase_status", purchase.get("status")) == "completed")
    is_premium = bool((profile or {}).get("is_premium"))
    is_owner = bool(profile_id and item.get("profile_id") == profile_id)
    approved = item.get("approval_status") == "approved" or item.get("moderation_status") == "approved"
    is_locked = bool(item.get("price_coins")) and not (has_purchased or is_owner)
    show_blur = bool(item.get("is_premium_locked")) and not (has_purchased or is_premium or is_owner)
    can_download = bool(item.get("download_enabled")) and approved and (has_purchased or is_owner or is_premium)
    return {
        "item": item,
        "can_download": can_download,
        "is_locked": is_locked,
        "has_purchased": has_purchased,
        "show_blur": show_blur,
        "is_owner": is_owner,
        "approved": approved,
        "purchase_id": (purchase or {}).get("id"),
    }


def purchase_item(buyer_profile_id, item_id):
    item = get_item(item_id)
    if not item:
        return False, "Item not found."
    if user_has_purchased_item(buyer_profile_id, item_id):
        return True, item

    wallet = get_or_create_wallet(buyer_profile_id)
    price_coins = _safe_int(item.get("price_coins"), 0)
    price_nad = item.get("price_nad") or (price_coins * COIN_VALUE_NAD)
    available = _safe_int(wallet.get("available_balance") or wallet.get("coin_balance"), 0)
    if price_coins > available:
        return False, "Insufficient coins."

    seller_wallet = get_or_create_wallet(item.get("profile_id"))
    seller_available = _safe_int(seller_wallet.get("available_balance") or seller_wallet.get("coin_balance"), 0)
    platform_fee = max(int(price_coins * PLATFORM_FEE_RATE), 0)
    seller_net = max(price_coins - platform_fee, 0)
    buyer_after = available - price_coins
    seller_after = seller_available + seller_net
    safe_update(
        "chain_wallets",
        {"available_balance": buyer_after, "coin_balance": buyer_after, "updated_at": _utcnow_iso()},
        eq={"profile_id": buyer_profile_id},
    )
    safe_update(
        "chain_wallets",
        {"available_balance": seller_after, "coin_balance": seller_after, "updated_at": _utcnow_iso()},
        eq={"profile_id": item.get("profile_id")},
    )
    purchase_rows = safe_insert(
        "chain_media_purchases",
        {
            "buyer_profile_id": buyer_profile_id,
            "item_id": item_id,
            "item_type": item.get("item_type"),
            "amount_nad": price_nad,
            "coins_spent": price_coins,
            "download_allowed": bool(item.get("download_enabled")),
            "purchase_status": "completed",
            "status": "completed",
            "created_at": _utcnow_iso(),
        },
    )
    purchase = purchase_rows[0] if purchase_rows else {"id": None}
    record_wallet_transaction(
        buyer_profile_id,
        "marketplace_purchase",
        "out",
        -price_coins,
        price_nad,
        related_table="chain_marketplace_items",
        related_id=item_id,
        description=f"Purchased {item.get('title') or 'marketplace item'}.",
        platform_fee_coins=platform_fee,
        net_coins=-price_coins,
        balance_before=available,
        balance_after=buyer_after,
    )
    record_wallet_transaction(
        item.get("profile_id"),
        "marketplace_sale",
        "in",
        seller_net,
        price_nad,
        related_table="chain_media_purchases",
        related_id=purchase.get("id"),
        description=f"Sale earned from {item.get('title') or 'marketplace item'}.",
        platform_fee_coins=platform_fee,
        net_coins=seller_net,
        balance_before=seller_available,
        balance_after=seller_after,
    )
    safe_update(
        "chain_marketplace_items",
        {
            "sales_count": _safe_int(item.get("sales_count"), 0) + 1,
            "total_earned_coins": _safe_int(item.get("total_earned_coins"), 0) + seller_net,
            "updated_at": _utcnow_iso(),
        },
        eq={"id": item_id},
    )
    safe_insert(
        "chain_platform_ledger",
        {
            "event_type": "marketplace_purchase",
            "source_table": "chain_media_purchases",
            "source_id": purchase.get("id"),
            "profile_id": item.get("profile_id"),
            "gross_coins": price_coins,
            "platform_fee_coins": platform_fee,
            "net_coins": seller_net,
            "amount_nad": price_nad,
            "description": f"Marketplace purchase for {item.get('title') or 'item'}.",
            "created_at": _utcnow_iso(),
        },
    )
    return True, item


def approve_marketplace_item(admin_id, item_id):
    item = get_item(item_id)
    if not item:
        return False, "Marketplace item not found."
    safe_update(
        "chain_marketplace_items",
        {
            "approval_status": "approved",
            "moderation_status": "approved",
            "is_public": True,
            "download_enabled": True,
            "approved_by": admin_id,
            "approved_at": _utcnow_iso(),
            "updated_at": _utcnow_iso(),
        },
        eq={"id": item_id},
    )
    log_admin_action(admin_id, "approve_marketplace_item", "marketplace_item", item_id, {"profile_id": item.get("profile_id")})
    return True, item


def approve_verification(admin_id, verification_id):
    rows = safe_select("chain_user_verifications", filters={"id": verification_id}, limit=1, order_by=None)
    if not rows:
        return False, "Verification not found."
    verification = rows[0]
    safe_update(
        "chain_user_verifications",
        {"verification_status": "approved", "updated_at": _utcnow_iso()},
        eq={"id": verification_id},
    )
    if verification.get("profile_id"):
        safe_update("chain_profiles", {"is_verified": True, "updated_at": _utcnow_iso()}, eq={"id": verification.get("profile_id")})
    log_admin_action(admin_id, "approve_verification", "user_verification", verification_id, {"profile_id": verification.get("profile_id")})
    return True, verification


def reject_verification(admin_id, verification_id, reason):
    rows = safe_select("chain_user_verifications", filters={"id": verification_id}, limit=1, order_by=None)
    if not rows:
        return False, "Verification not found."
    verification = rows[0]
    safe_update(
        "chain_user_verifications",
        {"verification_status": "rejected", "updated_at": _utcnow_iso(), "rejection_reason": reason},
        eq={"id": verification_id},
    )
    log_admin_action(admin_id, "reject_verification", "user_verification", verification_id, {"profile_id": verification.get("profile_id"), "reason": reason})
    return True, verification


def reject_marketplace_item(admin_id, item_id, reason):
    item = get_item(item_id)
    if not item:
        return False, "Marketplace item not found."
    safe_update(
        "chain_marketplace_items",
        {
            "approval_status": "rejected",
            "moderation_status": "rejected",
            "is_public": False,
            "rejected_by": admin_id,
            "rejected_at": _utcnow_iso(),
            "rejection_reason": reason,
            "updated_at": _utcnow_iso(),
        },
        eq={"id": item_id},
    )
    log_admin_action(admin_id, "reject_marketplace_item", "marketplace_item", item_id, {"reason": reason, "profile_id": item.get("profile_id")})
    return True, item


def feature_marketplace_item(admin_id, item_id):
    item = get_item(item_id)
    if not item:
        return False, "Marketplace item not found."
    safe_update("chain_marketplace_items", {"is_featured": True, "updated_at": _utcnow_iso()}, eq={"id": item_id})
    log_admin_action(admin_id, "feature_marketplace_item", "marketplace_item", item_id, {"profile_id": item.get("profile_id")})
    return True, item


def unfeature_marketplace_item(admin_id, item_id):
    item = get_item(item_id)
    if not item:
        return False, "Marketplace item not found."
    safe_update("chain_marketplace_items", {"is_featured": False, "updated_at": _utcnow_iso()}, eq={"id": item_id})
    log_admin_action(admin_id, "unfeature_marketplace_item", "marketplace_item", item_id, {"profile_id": item.get("profile_id")})
    return True, item
