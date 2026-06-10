import os, uuid, json
from datetime import datetime, timezone
from services.neon_service import fast_query, write_query, get_pool_status
from services.profile_service import get_profile_by_id

CATEGORIES_PRODUCT = [
    "electronics", "fashion", "home", "sports", "beauty",
    "food", "books", "toys", "health", "automotive",
    "pet_supplies", "office", "music", "art", "other",
]
CATEGORIES_SERVICE = [
    "hairdresser", "photographer", "nurse", "teacher", "mechanic",
    "driver", "cleaner", "chef", "trainer", "designer",
    "developer", "consultant", "translator", "other",
]
SHOP_TYPES = ["personal", "business", "creator"]
BOOKING_STATUSES = ["pending", "accepted", "rejected", "completed"]


def _db_available():
    if os.getenv("FLASK_TESTING") == "1" or os.getenv("CHAIN_FAST_LOCAL") == "1":
        return False
    status = get_pool_status()
    return bool(status.get("pool_ready") or status.get("recent_success") or status.get("configured"))


def _uuid(value=None):
    if value:
        try:
            return str(uuid.UUID(str(value)))
        except (TypeError, ValueError):
            pass
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


def _run(query, params=None, default=None):
    if not _db_available():
        return default or []
    try:
        return fast_query(query, params or (), default=default or [])
    except Exception:
        return default or []


def _write(query, params=None):
    if not _db_available():
        return {"ok": True}
    try:
        write_query(query, params or ())
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _row_to_dict(row):
    if not row:
        return None
    d = dict(row)
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


def _rows_to_list(rows):
    return [_row_to_dict(r) for r in rows]


def format_product(p):
    if not p:
        return None
    d = _row_to_dict(p)
    return d


def format_service(s):
    if not s:
        return None
    d = _row_to_dict(s)
    return d


def format_shop(s):
    if not s:
        return None
    d = _row_to_dict(s)
    return d


def format_booking(b):
    if not b:
        return None
    d = _row_to_dict(b)
    return d


def format_review(r):
    if not r:
        return None
    d = _row_to_dict(r)
    return d


# ─── SHOPS ───────────────────────────────────────────────────

def create_shop(profile_id, name, shop_type="personal", **kwargs):
    profile_id = _uuid(profile_id)
    sid = str(uuid.uuid4())
    existing = _run("SELECT id FROM chain_shops WHERE profile_id = %s LIMIT 1", (profile_id,))
    if existing:
        return {"ok": False, "error": "shop_already_exists", "shop_id": str(existing[0]["id"])}
    data = {
        "id": sid, "profile_id": profile_id, "shop_type": shop_type,
        "name": name, "description": kwargs.get("description", ""),
        "category": kwargs.get("category", "general"),
        "contact_email": kwargs.get("contact_email", ""),
        "contact_phone": kwargs.get("contact_phone", ""),
        "whatsapp": kwargs.get("whatsapp", ""),
        "location": kwargs.get("location", ""),
        "logo_url": kwargs.get("logo_url", ""),
        "banner_url": kwargs.get("banner_url", ""),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    vals = tuple(data.values())
    res = _write(f"INSERT INTO chain_shops ({cols}) VALUES ({placeholders})", vals)
    if not res.get("ok"):
        return res
    return {"ok": True, "shop": data}


def get_shop(shop_id):
    rows = _run("SELECT * FROM chain_shops WHERE id = %s LIMIT 1", (_uuid(shop_id),))
    return format_shop(rows[0]) if rows else None


def get_shop_by_profile(profile_id):
    rows = _run("SELECT * FROM chain_shops WHERE profile_id = %s LIMIT 1", (_uuid(profile_id),))
    return format_shop(rows[0]) if rows else None


def update_shop(shop_id, **kwargs):
    shop_id = _uuid(shop_id)
    allowed = ["name", "description", "category", "contact_email", "contact_phone",
               "whatsapp", "location", "logo_url", "banner_url", "is_active"]
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = %s")
            vals.append(v)
    if not sets:
        return {"ok": False, "error": "no_fields"}
    vals.append(shop_id)
    sets.append("updated_at = now()")
    _write(f"UPDATE chain_shops SET {', '.join(sets)} WHERE id = %s", tuple(vals))
    return {"ok": True}


def list_shops(category=None, limit=30, offset=0):
    if category:
        rows = _run(
            "SELECT * FROM chain_shops WHERE is_active = true AND category = %s ORDER BY rating DESC, created_at DESC LIMIT %s OFFSET %s",
            (category, limit, offset),
        )
    else:
        rows = _run(
            "SELECT * FROM chain_shops WHERE is_active = true ORDER BY rating DESC, created_at DESC LIMIT %s OFFSET %s",
            (limit, offset),
        )
    return _rows_to_list(rows)


def search_shops(query, limit=20):
    q = f"%{query}%"
    rows = _run(
        "SELECT * FROM chain_shops WHERE is_active = true AND (name ILIKE %s OR description ILIKE %s OR location ILIKE %s) ORDER BY rating DESC LIMIT %s",
        (q, q, q, limit),
    )
    return _rows_to_list(rows)


# ─── PRODUCTS ────────────────────────────────────────────────

def create_product(profile_id, shop_id, title, price_cents, **kwargs):
    profile_id = _uuid(profile_id)
    shop_id = _uuid(shop_id)
    pid = str(uuid.uuid4())
    stock = int(kwargs.get("stock", 0) or 0)
    data = {
        "id": pid, "shop_id": shop_id, "profile_id": profile_id,
        "title": title, "description": kwargs.get("description", ""),
        "images": kwargs.get("images", []),
        "price_cents": int(price_cents or 0),
        "stock": stock,
        "category": kwargs.get("category", "general"),
        "subcategory": kwargs.get("subcategory", ""),
        "location": kwargs.get("location", ""),
        "condition": kwargs.get("condition", "new"),
        "tags": kwargs.get("tags", []),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    vals = []
    for v in data.values():
        if isinstance(v, (list, dict)):
            vals.append(json.dumps(v))
        else:
            vals.append(v)
    res = _write(f"INSERT INTO chain_products ({cols}) VALUES ({placeholders})", tuple(vals))
    if res.get("ok"):
        _write("UPDATE chain_shops SET products_count = products_count + 1 WHERE id = %s", (shop_id,))
    return {"ok": True, "product": {**data, "id": pid}}


def get_product(product_id):
    rows = _run("SELECT * FROM chain_products WHERE id = %s LIMIT 1", (_uuid(product_id),))
    return format_product(rows[0]) if rows else None


def list_products(category=None, shop_id=None, limit=30, offset=0, sort="newest"):
    where = ["is_active = true"]
    params = []
    if category:
        where.append("category = %s")
        params.append(category)
    if shop_id:
        where.append("shop_id = %s")
        params.append(_uuid(shop_id))
    order = "created_at DESC" if sort == "newest" else "sales_count DESC" if sort == "trending" else "price_cents ASC"
    w = " AND ".join(where)
    rows = _run(
        f"SELECT * FROM chain_products WHERE {w} ORDER BY is_featured DESC, {order} LIMIT %s OFFSET %s",
        tuple(params + [limit, offset]),
    )
    return _rows_to_list(rows)


def search_products(query, category=None, min_price=None, max_price=None, limit=20):
    q = f"%{query}%"
    where = ["is_active = true", "(title ILIKE %s OR description ILIKE %s OR tags::text ILIKE %s)"]
    params = [q, q, q]
    if category:
        where.append("category = %s")
        params.append(category)
    if min_price is not None:
        where.append("price_cents >= %s")
        params.append(int(min_price))
    if max_price is not None:
        where.append("price_cents <= %s")
        params.append(int(max_price))
    w = " AND ".join(where)
    rows = _run(
        f"SELECT * FROM chain_products WHERE {w} ORDER BY is_featured DESC, created_at DESC LIMIT %s",
        tuple(params + [limit]),
    )
    return _rows_to_list(rows)


def save_product(profile_id, product_id):
    profile_id = _uuid(profile_id)
    product_id = _uuid(product_id)
    existing = _run("SELECT id FROM chain_saved_products WHERE profile_id = %s AND product_id = %s LIMIT 1", (profile_id, product_id))
    if existing:
        return {"ok": False, "error": "already_saved"}
    _write("INSERT INTO chain_saved_products (id, profile_id, product_id) VALUES (%s, %s, %s)", (str(uuid.uuid4()), profile_id, product_id))
    return {"ok": True}


def unsave_product(profile_id, product_id):
    _write("DELETE FROM chain_saved_products WHERE profile_id = %s AND product_id = %s", (_uuid(profile_id), _uuid(product_id)))
    return {"ok": True}


def list_saved_products(profile_id, limit=50):
    rows = _run(
        """SELECT sp.*, p.* FROM chain_saved_products sp
           JOIN chain_products p ON p.id = sp.product_id
           WHERE sp.profile_id = %s ORDER BY sp.created_at DESC LIMIT %s""",
        (_uuid(profile_id), limit),
    )
    return _rows_to_list(rows)


# ─── SERVICES ────────────────────────────────────────────────

def create_service(profile_id, shop_id, title, hourly_rate_cents, **kwargs):
    profile_id = _uuid(profile_id)
    shop_id = _uuid(shop_id)
    sid = str(uuid.uuid4())
    data = {
        "id": sid, "shop_id": shop_id, "profile_id": profile_id,
        "title": title, "description": kwargs.get("description", ""),
        "images": kwargs.get("images", []),
        "hourly_rate_cents": int(hourly_rate_cents or 0),
        "service_area": kwargs.get("service_area", ""),
        "availability": kwargs.get("availability", ""),
        "category": kwargs.get("category", "general"),
        "tags": kwargs.get("tags", []),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in data.values()]
    res = _write(f"INSERT INTO chain_services ({cols}) VALUES ({placeholders})", tuple(vals))
    if res.get("ok"):
        _write("UPDATE chain_shops SET services_count = services_count + 1 WHERE id = %s", (shop_id,))
    return {"ok": True, "service": {**data, "id": sid}}


def get_service(service_id):
    rows = _run("SELECT * FROM chain_services WHERE id = %s LIMIT 1", (_uuid(service_id),))
    return format_service(rows[0]) if rows else None


def list_services(category=None, shop_id=None, limit=30, offset=0):
    where = ["is_active = true"]
    params = []
    if category:
        where.append("category = %s")
        params.append(category)
    if shop_id:
        where.append("shop_id = %s")
        params.append(_uuid(shop_id))
    w = " AND ".join(where)
    rows = _run(
        f"SELECT * FROM chain_services WHERE {w} ORDER BY is_featured DESC, created_at DESC LIMIT %s OFFSET %s",
        tuple(params + [limit, offset]),
    )
    return _rows_to_list(rows)


def search_services(query, category=None, limit=20):
    q = f"%{query}%"
    where = ["is_active = true", "(title ILIKE %s OR description ILIKE %s OR tags::text ILIKE %s)"]
    params = [q, q, q]
    if category:
        where.append("category = %s")
        params.append(category)
    w = " AND ".join(where)
    rows = _run(
        f"SELECT * FROM chain_services WHERE {w} ORDER BY is_featured DESC, created_at DESC LIMIT %s",
        tuple(params + [limit]),
    )
    return _rows_to_list(rows)


# ─── BOOKINGS ────────────────────────────────────────────────

def create_booking(client_profile_id, service_id, **kwargs):
    client_profile_id = _uuid(client_profile_id)
    service_id = _uuid(service_id)
    svc = get_service(service_id)
    if not svc:
        return {"ok": False, "error": "service_not_found"}
    shop_id = svc.get("shop_id")
    provider_id = svc.get("profile_id")
    bid = str(uuid.uuid4())
    data = {
        "id": bid, "service_id": service_id, "shop_id": shop_id,
        "client_profile_id": client_profile_id,
        "provider_profile_id": provider_id,
        "status": "pending",
        "notes": kwargs.get("notes", ""),
        "client_notes": kwargs.get("client_notes", ""),
        "amount_cents": int(kwargs.get("amount_cents", svc.get("hourly_rate_cents", 0)) or 0),
        "requested_date": kwargs.get("requested_date") or _now().isoformat(),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    vals = list(data.values())
    res = _write(f"INSERT INTO chain_bookings ({cols}) VALUES ({placeholders})", tuple(vals))
    if not res.get("ok"):
        return res
    return {"ok": True, "booking": data}


def get_booking(booking_id):
    rows = _run("SELECT * FROM chain_bookings WHERE id = %s LIMIT 1", (_uuid(booking_id),))
    return format_booking(rows[0]) if rows else None


def update_booking_status(booking_id, status):
    booking_id = _uuid(booking_id)
    if status not in BOOKING_STATUSES:
        return {"ok": False, "error": f"invalid_status_{status}"}
    upd = {}
    upd["status"] = status
    if status == "completed":
        upd["completed_date"] = _now().isoformat()
    if status == "accepted":
        upd["scheduled_date"] = _now().isoformat()
    sets = ", ".join(f"{k} = %s" for k in upd)
    sets += ", updated_at = now()"
    vals = list(upd.values()) + [booking_id]
    _write(f"UPDATE chain_bookings SET {sets} WHERE id = %s", tuple(vals))
    return {"ok": True, "status": status}


def list_bookings(profile_id, role="client", status=None, limit=30, offset=0):
    col = "client_profile_id" if role == "client" else "provider_profile_id"
    where = [f"{col} = %s"]
    params = [_uuid(profile_id)]
    if status:
        where.append("status = %s")
        params.append(status)
    w = " AND ".join(where)
    rows = _run(
        f"SELECT * FROM chain_bookings WHERE {w} ORDER BY created_at DESC LIMIT %s OFFSET %s",
        tuple(params + [limit, offset]),
    )
    return _rows_to_list(rows)


# ─── REVIEWS ─────────────────────────────────────────────────

def create_review(reviewer_profile_id, **kwargs):
    reviewer_profile_id = _uuid(reviewer_profile_id)
    rid = str(uuid.uuid4())
    rating = int(kwargs.get("rating", 5) or 5)
    if rating < 1 or rating > 5:
        return {"ok": False, "error": "rating_must_be_1_5"}
    data = {
        "id": rid,
        "reviewer_profile_id": reviewer_profile_id,
        "target_profile_id": _uuid(kwargs["target_profile_id"]) if kwargs.get("target_profile_id") else None,
        "shop_id": _uuid(kwargs.get("shop_id")) if kwargs.get("shop_id") else None,
        "product_id": _uuid(kwargs.get("product_id")) if kwargs.get("product_id") else None,
        "service_id": _uuid(kwargs.get("service_id")) if kwargs.get("service_id") else None,
        "booking_id": _uuid(kwargs.get("booking_id")) if kwargs.get("booking_id") else None,
        "rating": rating,
        "title": kwargs.get("title", ""),
        "body": kwargs.get("body", ""),
        "image_url": kwargs.get("image_url", ""),
        "is_verified_purchase": bool(kwargs.get("is_verified_purchase", False)),
    }
    cols = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    vals = [json.dumps(v) if isinstance(v, (list, dict)) else v for v in data.values()]
    res = _write(f"INSERT INTO chain_reviews ({cols}) VALUES ({placeholders})", tuple(vals))
    if res.get("ok"):
        _update_review_aggregates(data)
    return {"ok": True, "review": data}


def _update_review_aggregates(data):
    if data.get("shop_id"):
        _recalc_rating("chain_shops", data["shop_id"])
    if data.get("product_id"):
        _recalc_rating("chain_products", data["product_id"])
    if data.get("service_id"):
        _recalc_rating("chain_services", data["service_id"])


def _recalc_rating(table, entity_id):
    col = {"chain_shops": "shop_id", "chain_products": "product_id", "chain_services": "service_id"}.get(table)
    if not col:
        return
    stats = _run(
        f"SELECT COUNT(*) AS cnt, COALESCE(AVG(rating), 0) AS avg FROM chain_reviews WHERE {col} = %s AND is_active = true",
        (entity_id,),
    )
    if stats:
        cnt = int(stats[0]["cnt"])
        avg = round(float(stats[0]["avg"] or 0), 2)
        _write(f"UPDATE {table} SET rating = %s, review_count = %s WHERE id = %s", (avg, cnt, entity_id))


def list_reviews(target_type, target_id, limit=20, offset=0):
    col = {"shop": "shop_id", "product": "product_id", "service": "service_id", "profile": "target_profile_id"}.get(target_type)
    if not col:
        return []
    rows = _run(
        f"SELECT * FROM chain_reviews WHERE {col} = %s AND is_active = true ORDER BY created_at DESC LIMIT %s OFFSET %s",
        (_uuid(target_id), limit, offset),
    )
    return _rows_to_list(rows)


# ─── SELLER DASHBOARD ────────────────────────────────────────

def get_seller_dashboard(profile_id):
    profile_id = _uuid(profile_id)
    shop = get_shop_by_profile(profile_id)
    result = {
        "shop": shop,
        "products_count": 0,
        "services_count": 0,
        "orders_count": 0,
        "bookings_count": 0,
        "total_earnings_cents": 0,
        "followers_count": 0,
        "views_count": 0,
        "recent_orders": [],
        "recent_bookings": [],
    }
    if not shop:
        return result
    shop_id = shop["id"]
    result["products_count"] = shop.get("products_count", 0)
    result["services_count"] = shop.get("services_count", 0)
    result["followers_count"] = shop.get("followers_count", 0)
    count = _run("SELECT COUNT(*) AS cnt FROM chain_products WHERE shop_id = %s AND is_active = true", (shop_id,))
    if count:
        result["products_count"] = int(count[0]["cnt"])
    svc = _run("SELECT COUNT(*) AS cnt FROM chain_services WHERE shop_id = %s AND is_active = true", (shop_id,))
    if svc:
        result["services_count"] = int(svc[0]["cnt"])
    bookings = _run("SELECT COUNT(*) AS cnt FROM chain_bookings WHERE shop_id = %s", (shop_id,))
    if bookings:
        result["bookings_count"] = int(bookings[0]["cnt"])
    earnings = _run("SELECT COALESCE(SUM(amount_cents), 0) AS total FROM chain_bookings WHERE shop_id = %s AND is_paid = true", (shop_id,))
    if earnings:
        result["total_earnings_cents"] = int(earnings[0]["total"])
    recent_b = _run("SELECT * FROM chain_bookings WHERE shop_id = %s ORDER BY created_at DESC LIMIT 10", (shop_id,))
    if recent_b:
        result["recent_bookings"] = _rows_to_list(recent_b)
    result["shop_id"] = shop_id
    return result


# ─── SEARCH ──────────────────────────────────────────────────

def marketplace_search(query, category=None, min_price=None, max_price=None, location=None, verified_only=False, limit=20):
    products = search_products(query, category, min_price, max_price, limit)
    services = search_services(query, category, limit)
    shops = search_shops(query, limit)
    if verified_only:
        shops = [s for s in shops if s.get("is_verified")]
    return {
        "products": products,
        "services": services,
        "shops": shops,
    }


# ─── SAVE/SHARE HELPERS ──────────────────────────────────────

def toggle_save(profile_id, item_type, item_id):
    if item_type == "product":
        return save_product(profile_id, item_id)
    elif item_type == "service":
        profile_id = _uuid(profile_id)
        item_id = _uuid(item_id)
        existing = _run("SELECT id FROM chain_saved_products WHERE profile_id = %s AND service_id = %s LIMIT 1", (profile_id, item_id))
        if existing:
            return {"ok": False, "error": "already_saved"}
        _write("INSERT INTO chain_saved_products (id, profile_id, service_id) VALUES (%s, %s, %s)", (str(uuid.uuid4()), profile_id, item_id))
        return {"ok": True}
    return {"ok": False, "error": "unknown_type"}
