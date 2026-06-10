#!/usr/bin/env python3
"""Phase 62 — Seed marketplace shops, products, services, reviews."""
import os, sys, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["FLASK_TESTING"] = "1"

from services.neon_service import write_query, fast_query

SEED_PROFILES = ["chain_star", "chain_moon", "chain_premium"]
SHOP_NAMES = ["Star Emporium", "Moonlight Boutique", "Premium Hub"]
SHOP_TYPES = ["creator", "business", "personal"]
SHOP_CATS = ["fashion", "electronics", "general"]

PRODUCTS_DATA = [
    ("Wireless Headphones", "electronics", 2999, 50, "new", ["audio", "wireless", "bluetooth"]),
    ("Leather Jacket", "fashion", 8999, 20, "new", ["leather", "jacket", "men"]),
    ("Smart Watch", "electronics", 14999, 30, "new", ["smartwatch", "fitness", "gps"]),
    ("Designer Sunglasses", "fashion", 3999, 100, "new", ["designer", "uv", "accessory"]),
    ("Bluetooth Speaker", "electronics", 4999, 40, "new", ["speaker", "bluetooth", "portable"]),
    ("Running Shoes", "fashion", 5999, 60, "new", ["shoes", "running", "sports"]),
    ("Tablet Stand", "electronics", 1999, 200, "new", ["stand", "tablet", "desk"]),
    ("Silk Scarf", "fashion", 2499, 80, "new", ["silk", "scarf", "luxury"]),
    ("USB-C Hub", "electronics", 3499, 150, "new", ["usb", "hub", "adapter"]),
    ("Denim Jeans", "fashion", 4999, 45, "new", ["denim", "jeans", "casual"]),
    ("Mechanical Keyboard", "electronics", 7999, 25, "new", ["keyboard", "mechanical", "gaming"]),
    ("Canvas Backpack", "fashion", 3999, 70, "new", ["backpack", "canvas", "travel"]),
    ("Webcam HD", "electronics", 4499, 35, "new", ["webcam", "hd", "streaming"]),
    ("Wool Beanie", "fashion", 1499, 120, "new", ["beanie", "wool", "winter"]),
    ("Portable Charger", "electronics", 2999, 90, "new", ["charger", "portable", "battery"]),
    ("Cotton T-Shirt", "fashion", 1999, 200, "new", ["tshirt", "cotton", "basic"]),
    ("Mouse Pad XL", "electronics", 999, 300, "new", ["mousepad", "gaming", "desk"]),
    ("Hoodie", "fashion", 5499, 55, "new", ["hoodie", "casual", "cotton"]),
    ("Laptop Sleeve", "electronics", 2499, 65, "new", ["sleeve", "laptop", "protection"]),
    ("Leather Belt", "fashion", 2999, 85, "new", ["belt", "leather", "accessory"]),
]

SERVICES_DATA = [
    ("Professional Hair Styling", "hairdresser", 15000, "Windhoek", "Mon-Fri 9am-5pm"),
    ("Event Photography", "photographer", 25000, "Windhoek", "Weekends & evenings"),
    ("Private Nursing Care", "nurse", 20000, "Windhoek", "24/7 availability"),
    ("Mathematics Tutoring", "teacher", 8000, "Online", "Afternoons & weekends"),
    ("Car Repair & Maintenance", "mechanic", 18000, "Windhoek", "Mon-Sat 8am-6pm"),
    ("Professional Driving Services", "driver", 12000, "Windhoek", "Any time"),
    ("Deep Cleaning Service", "cleaner", 10000, "Windhoek", "Mon-Fri"),
    ("Personal Chef", "chef", 30000, "Windhoek", "By appointment"),
    ("Fitness Training", "trainer", 15000, "Windhoek", "Mornings & evenings"),
    ("Graphic Design", "designer", 20000, "Remote", "Flexible hours"),
]


def seed():
    print("Seeding Phase 62 marketplace data...")
    profile_ids = {}
    for uname in SEED_PROFILES:
        rows = fast_query("SELECT id FROM chain_profiles WHERE username = %s LIMIT 1", (uname,), default=[])
        if rows:
            profile_ids[uname] = str(rows[0]["id"])
            print(f"  Found {uname}: {profile_ids[uname]}")
    if len(profile_ids) < 2:
        print("  Need at least 2 seeded profiles. Run seed_chain_test_users.py first.")
        return

    # Create shops
    shop_ids = {}
    for i, (uname, sname, stype, scat) in enumerate(zip(SEED_PROFILES, SHOP_NAMES, SHOP_TYPES, SHOP_CATS)):
        pid = profile_ids.get(uname)
        if not pid:
            continue
        existing = fast_query("SELECT id FROM chain_shops WHERE profile_id = %s LIMIT 1", (pid,), default=[])
        if existing:
            sid = str(existing[0]["id"])
            print(f"  Shop already exists for {uname}: {sid}")
            shop_ids[uname] = sid
            continue
        sid = os.urandom(16).hex()
        sid_uuid = f"{sid[:8]}-{sid[8:12]}-{sid[12:16]}-{sid[16:20]}-{sid[20:32]}"
        write_query(
            "INSERT INTO chain_shops (id, profile_id, shop_type, name, category, description) VALUES (%s, %s, %s, %s, %s, %s)",
            (sid_uuid, pid, stype, sname, scat, f"{sname} — your destination for quality {scat}."),
        )
        shop_ids[uname] = sid_uuid
        print(f"  Created shop {sname} for {uname}")

    # Create products
    for i, (title, cat, price, stock, cond, tags) in enumerate(PRODUCTS_DATA):
        shop_uname = SEED_PROFILES[i % 3]
        shop_id = shop_ids.get(shop_uname)
        pid = profile_ids.get(shop_uname)
        if not shop_id or not pid:
            continue
        existing = fast_query("SELECT id FROM chain_products WHERE title = %s AND shop_id = %s LIMIT 1", (title, shop_id), default=[])
        if existing:
            continue
        prod_id = os.urandom(16).hex()
        prod_uuid = f"{prod_id[:8]}-{prod_id[8:12]}-{prod_id[12:16]}-{prod_id[16:20]}-{prod_id[20:32]}"
        write_query(
            "INSERT INTO chain_products (id, shop_id, profile_id, title, description, price_cents, stock, category, condition, tags) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (prod_uuid, shop_id, pid, title, f"High-quality {title.lower()} available now.", price, stock, cat, cond, json.dumps(tags)),
        )
        write_query("UPDATE chain_shops SET products_count = products_count + 1 WHERE id = %s", (shop_id,))
    print(f"  Created/verified {len(PRODUCTS_DATA)} products")

    # Create services
    for i, (title, cat, rate, area, avail) in enumerate(SERVICES_DATA):
        shop_uname = SEED_PROFILES[i % 3]
        shop_id = shop_ids.get(shop_uname)
        pid = profile_ids.get(shop_uname)
        if not shop_id or not pid:
            continue
        existing = fast_query("SELECT id FROM chain_services WHERE title = %s AND shop_id = %s LIMIT 1", (title, shop_id), default=[])
        if existing:
            continue
        svc_id = os.urandom(16).hex()
        svc_uuid = f"{svc_id[:8]}-{svc_id[8:12]}-{svc_id[12:16]}-{svc_id[16:20]}-{svc_id[20:32]}"
        write_query(
            "INSERT INTO chain_services (id, shop_id, profile_id, title, description, hourly_rate_cents, service_area, availability, category) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (svc_uuid, shop_id, pid, title, f"Professional {title.lower()} service.", rate, area, avail, cat),
        )
        write_query("UPDATE chain_shops SET services_count = services_count + 1 WHERE id = %s", (shop_id,))
    print(f"  Created/verified {len(SERVICES_DATA)} services")

    print("Seeding complete.")


if __name__ == "__main__":
    seed()
