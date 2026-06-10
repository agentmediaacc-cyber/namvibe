#!/usr/bin/env python3
"""Seed Phase 65: wallet payments, payout methods, transactions, ledger entries."""

import os, sys, json, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from datetime import datetime, timezone
from uuid import uuid4

os.environ['FLASK_TESTING'] = '1'
os.environ['CHAIN_FAST_LOCAL'] = '1'

from app import app
from services.neon_service import fast_query, write_query
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_delete
from services.wallet_service import get_or_create_wallet, credit_wallet, debit_wallet, get_wallet
from services.wallet_payment_service import (
    add_payout_method, deposit_wallet, send_tip, send_gift,
    pay_subscription, marketplace_purchase, get_balance_summary, get_earnings_breakdown
)

PROFILES = ['chain_star', 'chain_moon', 'chain_premium', 'chain_gold', 'chain_million']
SEED_AMOUNT = 50000  # 500 coins for each profile

def _utcnow():
    return datetime.now(timezone.utc).isoformat()

def seed():
    print("🌱 Seeding Phase 65 wallet data...")

    # 1. Ensure wallets exist and seed balances
    for pid in PROFILES:
        w = get_or_create_wallet(pid)
        if not w:
            print(f"  ❌ Could not create wallet for {pid}")
            continue
        bal = get_wallet(pid)
        current = (bal.get('balance_cents') or 0) if bal else 0
        if current < SEED_AMOUNT:
            add = SEED_AMOUNT - current
            r = credit_wallet(pid, add, description=f'Seed deposit for {pid}', transaction_type='deposit')
            if r.get('ok'):
                print(f"  ✅ {pid}: deposited {add} coins (balance was {current})")
            else:
                print(f"  ❌ {pid}: deposit failed — {r.get('error')}")
        else:
            print(f"  ✅ {pid}: already has {current} coins (≥ {SEED_AMOUNT})")

    # 2. Add payout methods for profiles
    pm_data = [
        ('chain_star', 'bank', 'Alice Namib', '****1234', True),
        ('chain_moon', 'mobile_wallet', 'Bob Wallet', '****5678', True),
        ('chain_premium', 'paypal', 'charlie@email.com', 'charlie@***.com', True),
        ('chain_gold', 'bank', 'Diana Account', '****9012', True),
        ('chain_million', 'bank', 'Eve Banking', '****3456', True),
    ]
    for pid, prov, name, masked, default in pm_data:
        existing = safe_select('chain_payout_methods', limit=1, filters={'profile_id': pid, 'provider': prov})
        if existing:
            print(f"  ℹ️  {pid}: {prov} payout method already exists")
            continue
        r = add_payout_method(pid, prov, name, masked, is_default=default)
        if r.get('ok'):
            print(f"  ✅ {pid}: added {prov} payout method")
        else:
            print(f"  ❌ {pid}: add payout method failed — {r.get('error')}")

    # 3. Create some transactions between profiles
    # Tips: star -> moon, premium -> gold
    tip_tests = [
        ('chain_star', 'chain_moon', 500, 'Great content!'),
        ('chain_premium', 'chain_gold', 300, 'Awesome work'),
        ('chain_million', 'chain_star', 1000, 'Keep it up!'),
    ]
    for sender, receiver, amount, msg in tip_tests:
        r = send_tip(sender, receiver, amount, message=msg)
        if r.get('ok'):
            print(f"  ✅ {sender} tipped {receiver} {amount} coins")
        else:
            print(f"  ❌ {sender} -> {receiver}: {r.get('error')}")

    # Gifts: moon -> premium, gold -> star
    gifts = safe_select('chain_gift_catalog', limit=5)
    if gifts:
        g2 = [
            ('chain_moon', 'chain_premium', gifts[0]['id']),
            ('chain_gold', 'chain_star', gifts[1]['id'] if len(gifts) > 1 else gifts[0]['id']),
        ]
        for sender, receiver, gid in g2:
            r = send_gift(sender, receiver, gid)
            if r.get('ok'):
                print(f"  ✅ {sender} gifted {receiver} (gift {gid})")
            else:
                print(f"  ❌ {sender} gift -> {receiver}: {r.get('error')}")

    # Subscriptions: star -> premium, moon -> gold
    subs = [
        ('chain_star', 'chain_premium', 999, 'basic'),
        ('chain_moon', 'chain_gold', 1999, 'premium'),
    ]
    for sub, creator, price, tier in subs:
        r = pay_subscription(sub, creator, price, tier=tier)
        if r.get('ok'):
            print(f"  ✅ {sub} subscribed to {creator} ({tier}, {price} coins)")
        else:
            print(f"  ❌ {sub} -> {creator} sub: {r.get('error')}")

    # Marketplace purchases
    purchases = [
        ('chain_premium', 'chain_million', 2500, 'item_001', 'digital'),
        ('chain_gold', 'chain_star', 1500, 'item_002', 'product'),
    ]
    for buyer, seller, amount, item_id, item_type in purchases:
        r = marketplace_purchase(buyer, seller, amount, item_id=item_id, item_type=item_type)
        if r.get('ok'):
            print(f"  ✅ {buyer} purchased from {seller} ({amount} coins)")
        else:
            print(f"  ❌ {buyer} -> {seller} purchase: {r.get('error')}")

    # 4. Generate ledger entries from existing transactions
    from services.wallet_payment_service import _create_ledger_entry
    for pid in PROFILES:
        w = get_wallet(pid)
        if w:
            _create_ledger_entry(
                pid, w.get('id'), None, 'seed',
                0, w.get('balance_cents', 0), w.get('balance_cents', 0),
                w.get('pending_balance_cents', 0), w.get('pending_balance_cents', 0),
                description=f'Seed ledger entry for {pid}'
            )
            print(f"  ✅ {pid}: ledger entry created")

    # 5. Deposit some extra coins to replenish for testing
    for pid in ['chain_star', 'chain_moon', 'chain_premium']:
        r = deposit_wallet(pid, 10000)
        if r.get('ok'):
            print(f"  ✅ {pid}: deposited 100.00 coins (test funds)")
        else:
            print(f"  ❌ {pid}: deposit failed — {r.get('error')}")

    print("\n✅ Phase 65 seeding complete!")

if __name__ == '__main__':
    seed()
