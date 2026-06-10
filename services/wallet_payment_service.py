import os
import json
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from services.neon_service import fast_query, write_query, get_pool_status
from services.supabase_safe import safe_insert, safe_select, safe_update, safe_delete
from services.profile_service import get_current_profile

PLATFORM_FEE_PCT = 5


def _db_available():
    if os.getenv('FLASK_TESTING') == '1' or os.getenv('CHAIN_FAST_LOCAL') == '1':
        return False
    status = get_pool_status()
    return bool(status.get('pool_ready') or status.get('recent_success') or status.get('configured'))


def _utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def _int_cents(value):
    try:
        return int(round(float(value)))
    except (TypeError, ValueError, OverflowError):
        return 0


def _make_idempotency_key(action, profile_id, *parts):
    raw = action + ':' + profile_id + ':' + ':'.join(str(p) for p in parts)
    return hashlib.sha256(raw.encode()).hexdigest()


def _check_idempotency(key, profile_id, action_type):
    if not key:
        return None
    rows = safe_select('chain_wallet_idempotency_keys', limit=1, filters={'idempotency_key': key, 'profile_id': profile_id, 'action_type': action_type}, order_by=None)
    return rows[0] if rows else None


def _record_idempotency(key, profile_id, action_type, request_hash=None, status_code=200):
    if not key:
        return None
    payload = {'idempotency_key': key, 'profile_id': profile_id, 'action_type': action_type, 'request_hash': request_hash, 'response_status': status_code, 'created_at': _utcnow_iso()}
    return safe_insert('chain_wallet_idempotency_keys', payload)


def _create_ledger_entry(profile_id, wallet_id, transaction_id, entry_type, amount_cents, balance_before, balance_after, pending_before, pending_after, status='completed', reference_type=None, reference_id=None, description=None):
    payload = {
        'profile_id': profile_id,
        'wallet_id': wallet_id,
        'transaction_id': transaction_id,
        'entry_type': entry_type,
        'amount_cents': _int_cents(amount_cents),
        'balance_before_cents': _int_cents(balance_before),
        'balance_after_cents': _int_cents(balance_after),
        'pending_before_cents': _int_cents(pending_before),
        'pending_after_cents': _int_cents(pending_after),
        'status': status,
        'reference_type': reference_type,
        'reference_id': reference_id,
        'description': description,
        'created_at': _utcnow_iso(),
    }
    return safe_insert('chain_wallet_ledger_entries', payload)


def _notify(profile_id, title, body, n_type='wallet', entity_id=None, action_url=None):
    try:
        from services.notification_engine import create_notification
        create_notification(recipient_profile_id=profile_id, actor_profile_id=profile_id, event_type=n_type, title=title, body=body, entity_type='wallet', entity_id=entity_id, action_url=action_url)
    except Exception:
        try:
            from services.notification_service import create_notification
            create_notification(profile_id=profile_id, title=title, body=body, n_type=n_type, link_url=action_url)
        except Exception:
            pass


# ─── Validation ───

def validate_amount_cents(amount_cents):
    val = _int_cents(amount_cents)
    if val <= 0:
        return False, 'Amount must be positive'
    return True, val


def apply_platform_fee(amount_cents):
    fee = _int_cents(amount_cents * PLATFORM_FEE_PCT / 100)
    net = _int_cents(amount_cents - fee)
    return fee, net


# ─── Wallet Core ───

def get_or_create_wallet(profile_id):
    from services.wallet_service import get_or_create_wallet as _orig
    return _orig(profile_id)


def get_balance(profile_id):
    from services.wallet_service import get_wallet as _orig
    w = _orig(profile_id)
    if not w:
        w = get_or_create_wallet(profile_id)
    if not w:
        return {'balance_cents': 0, 'pending_balance_cents': 0, 'withdrawable_balance_cents': 0, 'lifetime_earned_cents': 0, 'lifetime_spent_cents': 0, 'currency': 'NAD', 'status': 'active'}
    return w


def list_transactions(profile_id, page=1, limit=20, tx_type=None, status=None):
    from services.wallet_service import get_wallet_transactions as _orig
    offset = (page - 1) * limit
    return _orig(profile_id, limit=limit, offset=offset, transaction_type=tx_type)


# ─── Balance Summary ───

def get_balance_summary(profile_id):
    w = get_balance(profile_id)
    if not w:
        return {'available': 0, 'pending': 0, 'withdrawable': 0, 'total_earned': 0, 'total_spent': 0}
    available = _int_cents(w.get('balance_cents', 0))
    pending = _int_cents(w.get('pending_balance_cents', 0))
    withdrawable = _int_cents(w.get('withdrawable_balance_cents', 0))
    total_earned = _int_cents(w.get('lifetime_earned_cents', 0))
    total_spent = _int_cents(w.get('lifetime_spent_cents', 0))
    if withdrawable == 0:
        withdrawable = available
    return {'available': available, 'pending': pending, 'withdrawable': withdrawable, 'total_earned': total_earned, 'total_spent': total_spent}


def get_earnings_breakdown(profile_id):
    txs = list_transactions(profile_id, limit=200)
    breakdown = {'tips': 0, 'gifts': 0, 'subscriptions': 0, 'marketplace': 0, 'other': 0}
    for t in txs:
        tt = t.get('transaction_type', '')
        amt = _int_cents(t.get('amount_cents', 0))
        if 'tip' in tt:
            breakdown['tips'] += amt
        elif 'gift' in tt:
            breakdown['gifts'] += amt
        elif 'subscription' in tt:
            breakdown['subscriptions'] += amt
        elif 'marketplace' in tt or 'sale' in tt:
            breakdown['marketplace'] += amt
        else:
            breakdown['other'] += amt
    return breakdown


# ─── Transfer ───

def transfer_between_wallets(from_profile_id, to_profile_id, amount_cents, description='', reference_type=None, reference_id=None):
    if from_profile_id == to_profile_id:
        return {'ok': False, 'error': 'Cannot transfer to yourself'}
    val_ok, val = validate_amount_cents(amount_cents)
    if not val_ok:
        return {'ok': False, 'error': val}
    from services.wallet_service import debit_wallet, credit_wallet
    sender_before = get_balance(from_profile_id)
    debit = debit_wallet(from_profile_id, val, description='Transfer: ' + description, transaction_type='transfer_out', reference_type=reference_type, reference_id=reference_id, counterparty_profile_id=to_profile_id)
    if not debit.get('ok'):
        return debit
    credit = credit_wallet(to_profile_id, val, description='Transfer: ' + description, transaction_type='transfer_in', reference_type=reference_type, reference_id=reference_id, counterparty_profile_id=from_profile_id)
    if not credit.get('ok'):
        credit_wallet(from_profile_id, val, description='Reversal: ' + description, transaction_type='reversal', reference_type=reference_type, reference_id=reference_id)
        return {'ok': False, 'error': 'Credit failed, transfer reversed'}
    sender_after = get_balance(from_profile_id)
    _create_ledger_entry(from_profile_id, None, debit.get('transaction_id'), 'adjustment', -val, _int_cents(sender_before.get('balance_cents', 0)), _int_cents(sender_after.get('balance_cents', 0)), _int_cents(sender_before.get('pending_balance_cents', 0)), _int_cents(sender_after.get('pending_balance_cents', 0)), reference_type=reference_type, reference_id=reference_id, description=description)
    return {'ok': True, 'transaction_id': debit.get('transaction_id')}


# ─── Tips ───

def send_tip(sender_profile_id, receiver_profile_id, amount_cents, message='', idempotency_key=None):
    if sender_profile_id == receiver_profile_id:
        return {'ok': False, 'error': 'Cannot tip yourself'}
    val_ok, val = validate_amount_cents(amount_cents)
    if not val_ok:
        return {'ok': False, 'error': val}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, sender_profile_id, 'tip')
        if existing:
            return {'ok': True, 'idempotent': True, 'transaction_id': existing.get('id')}
    from services.wallet_service import debit_wallet, credit_wallet
    sender_before = get_balance(sender_profile_id)
    fee, net = apply_platform_fee(val)
    debit = debit_wallet(sender_profile_id, val, description='Tip: ' + (message or 'No message'), transaction_type='tip_sent', reference_type='tip', counterparty_profile_id=receiver_profile_id)
    if not debit.get('ok'):
        return debit
    receiver_before = get_balance(receiver_profile_id)
    credit = credit_wallet(receiver_profile_id, net, description='Tip received: ' + (message or 'No message'), transaction_type='tip_received', reference_type='tip', counterparty_profile_id=sender_profile_id)
    if not credit.get('ok'):
        credit_wallet(sender_profile_id, val, description='Reversal: tip failed', transaction_type='reversal')
        return {'ok': False, 'error': 'Tip failed, funds returned'}
    if fee > 0:
        _create_ledger_entry(sender_profile_id, None, debit.get('transaction_id'), 'platform_fee', fee, 0, 0, 0, 0, description='Platform fee on tip')
    sender_after = get_balance(sender_profile_id)
    receiver_after = get_balance(receiver_profile_id)
    _create_ledger_entry(sender_profile_id, None, debit.get('transaction_id'), 'tip_sent', -val, _int_cents(sender_before.get('balance_cents', 0)), _int_cents(sender_after.get('balance_cents', 0)), _int_cents(sender_before.get('pending_balance_cents', 0)), _int_cents(sender_after.get('pending_balance_cents', 0)), reference_type='tip', description=message)
    _create_ledger_entry(receiver_profile_id, None, credit.get('transaction_id'), 'tip_received', net, _int_cents(receiver_before.get('balance_cents', 0)), _int_cents(receiver_after.get('balance_cents', 0)), _int_cents(receiver_before.get('pending_balance_cents', 0)), _int_cents(receiver_after.get('pending_balance_cents', 0)), reference_type='tip', description=message)
    if idempotency_key:
        _record_idempotency(idempotency_key, sender_profile_id, 'tip')
    _notify(receiver_profile_id, 'Tip Received', 'You received a tip of ' + str(val) + ' coins!', n_type='tip', entity_id=debit.get('transaction_id'), action_url='/wallet')
    return {'ok': True, 'transaction_id': debit.get('transaction_id'), 'amount_cents': val, 'fee_cents': fee, 'net_cents': net}


# ─── Gifts ───

def send_gift(sender_profile_id, receiver_profile_id, gift_id, idempotency_key=None):
    if sender_profile_id == receiver_profile_id:
        return {'ok': False, 'error': 'Cannot gift yourself'}
    gift_rows = safe_select('chain_gift_catalog', limit=1, filters={'id': gift_id, 'is_active': True}, order_by=None)
    if not gift_rows:
        gift_rows = safe_select('chain_gift_catalog', limit=1, filters={'id': gift_id}, order_by=None)
        if not gift_rows:
            return {'ok': False, 'error': 'Gift not found'}
    gift = gift_rows[0]
    price = _int_cents(gift.get('coin_price', 0))
    if price <= 0:
        return {'ok': False, 'error': 'Invalid gift price'}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, sender_profile_id, 'gift')
        if existing:
            return {'ok': True, 'idempotent': True, 'transaction_id': existing.get('id')}
    from services.wallet_service import debit_wallet, credit_wallet
    sender_before = get_balance(sender_profile_id)
    fee, net = apply_platform_fee(price)
    debit = debit_wallet(sender_profile_id, price, description='Gift: ' + gift.get('gift_name', 'Gift'), transaction_type='gift_sent', reference_type='gift', reference_id=gift_id, counterparty_profile_id=receiver_profile_id)
    if not debit.get('ok'):
        return debit
    receiver_before = get_balance(receiver_profile_id)
    credit = credit_wallet(receiver_profile_id, net, description='Gift received: ' + gift.get('gift_name', 'Gift'), transaction_type='gift_received', reference_type='gift', reference_id=gift_id, counterparty_profile_id=sender_profile_id)
    if not credit.get('ok'):
        credit_wallet(sender_profile_id, price, description='Reversal: gift failed', transaction_type='reversal')
        return {'ok': False, 'error': 'Gift failed, funds returned'}
    if fee > 0:
        _create_ledger_entry(sender_profile_id, None, debit.get('transaction_id'), 'platform_fee', fee, 0, 0, 0, 0, description='Platform fee on gift')
    sender_after = get_balance(sender_profile_id)
    receiver_after = get_balance(receiver_profile_id)
    _create_ledger_entry(sender_profile_id, None, debit.get('transaction_id'), 'gift_sent', -price, _int_cents(sender_before.get('balance_cents', 0)), _int_cents(sender_after.get('balance_cents', 0)), _int_cents(sender_before.get('pending_balance_cents', 0)), _int_cents(sender_after.get('pending_balance_cents', 0)), reference_type='gift', reference_id=gift_id, description=gift.get('gift_name'))
    _create_ledger_entry(receiver_profile_id, None, credit.get('transaction_id'), 'gift_received', net, _int_cents(receiver_before.get('balance_cents', 0)), _int_cents(receiver_after.get('balance_cents', 0)), _int_cents(receiver_before.get('pending_balance_cents', 0)), _int_cents(receiver_after.get('pending_balance_cents', 0)), reference_type='gift', reference_id=gift_id, description=gift.get('gift_name'))
    if idempotency_key:
        _record_idempotency(idempotency_key, sender_profile_id, 'gift')
    _notify(receiver_profile_id, 'Gift Received', 'You received ' + gift.get('gift_name', 'a gift') + '!', n_type='gift', entity_id=debit.get('transaction_id'), action_url='/wallet')
    return {'ok': True, 'transaction_id': debit.get('transaction_id'), 'amount_cents': price, 'fee_cents': fee, 'net_cents': net, 'gift': gift}


# ─── Subscriptions ───

def pay_subscription(subscriber_profile_id, creator_profile_id, amount_cents, tier='basic', idempotency_key=None):
    if subscriber_profile_id == creator_profile_id:
        return {'ok': False, 'error': 'Cannot subscribe to yourself'}
    val_ok, val = validate_amount_cents(amount_cents)
    if not val_ok:
        return {'ok': False, 'error': val}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, subscriber_profile_id, 'subscription')
        if existing:
            return {'ok': True, 'idempotent': True, 'transaction_id': existing.get('id')}
    from services.wallet_service import debit_wallet, credit_wallet
    subscriber_before = get_balance(subscriber_profile_id)
    fee, net = apply_platform_fee(val)
    debit = debit_wallet(subscriber_profile_id, val, description='Subscription: ' + tier, transaction_type='subscription_payment', reference_type='subscription', counterparty_profile_id=creator_profile_id)
    if not debit.get('ok'):
        return debit
    creator_before = get_balance(creator_profile_id)
    credit = credit_wallet(creator_profile_id, net, description='Subscription received: ' + tier, transaction_type='subscription_received', reference_type='subscription', counterparty_profile_id=subscriber_profile_id)
    if not credit.get('ok'):
        credit_wallet(subscriber_profile_id, val, description='Reversal: subscription failed', transaction_type='reversal')
        return {'ok': False, 'error': 'Subscription failed, funds returned'}
    if fee > 0:
        _create_ledger_entry(subscriber_profile_id, None, debit.get('transaction_id'), 'platform_fee', fee, 0, 0, 0, 0, description='Platform fee on subscription')
    _create_ledger_entry(subscriber_profile_id, None, debit.get('transaction_id'), 'subscription_payment', -val, _int_cents(subscriber_before.get('balance_cents', 0)), _int_cents(get_balance(subscriber_profile_id).get('balance_cents', 0)), _int_cents(subscriber_before.get('pending_balance_cents', 0)), _int_cents(get_balance(subscriber_profile_id).get('pending_balance_cents', 0)), reference_type='subscription', description=tier)
    _create_ledger_entry(creator_profile_id, None, credit.get('transaction_id'), 'subscription_received', net, _int_cents(creator_before.get('balance_cents', 0)), _int_cents(get_balance(creator_profile_id).get('balance_cents', 0)), _int_cents(creator_before.get('pending_balance_cents', 0)), _int_cents(get_balance(creator_profile_id).get('pending_balance_cents', 0)), reference_type='subscription', description=tier)
    if idempotency_key:
        _record_idempotency(idempotency_key, subscriber_profile_id, 'subscription')
    _notify(creator_profile_id, 'New Subscription', 'You have a new ' + tier + ' subscriber!', n_type='subscription', entity_id=debit.get('transaction_id'), action_url='/wallet')
    return {'ok': True, 'transaction_id': debit.get('transaction_id'), 'amount_cents': val, 'fee_cents': fee, 'net_cents': net}


# ─── Marketplace Purchase ───

def marketplace_purchase(buyer_profile_id, seller_profile_id, amount_cents, item_id=None, item_type='product', idempotency_key=None):
    if buyer_profile_id == seller_profile_id:
        return {'ok': False, 'error': 'Cannot purchase from yourself'}
    val_ok, val = validate_amount_cents(amount_cents)
    if not val_ok:
        return {'ok': False, 'error': val}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, buyer_profile_id, 'marketplace_purchase')
        if existing:
            return {'ok': True, 'idempotent': True, 'transaction_id': existing.get('id')}
    from services.wallet_service import debit_wallet, credit_wallet
    buyer_before = get_balance(buyer_profile_id)
    fee, net = apply_platform_fee(val)
    debit = debit_wallet(buyer_profile_id, val, description='Purchase: ' + item_type, transaction_type='marketplace_purchase', reference_type=item_type, reference_id=item_id, counterparty_profile_id=seller_profile_id)
    if not debit.get('ok'):
        return debit
    seller_before = get_balance(seller_profile_id)
    credit = credit_wallet(seller_profile_id, net, description='Sale: ' + item_type, transaction_type='marketplace_sale', reference_type=item_type, reference_id=item_id, counterparty_profile_id=buyer_profile_id)
    if not credit.get('ok'):
        credit_wallet(buyer_profile_id, val, description='Reversal: purchase failed', transaction_type='reversal')
        return {'ok': False, 'error': 'Purchase failed, funds returned'}
    if fee > 0:
        _create_ledger_entry(buyer_profile_id, None, debit.get('transaction_id'), 'platform_fee', fee, 0, 0, 0, 0, description='Platform fee on purchase')
    _create_ledger_entry(buyer_profile_id, None, debit.get('transaction_id'), 'marketplace_purchase', -val, _int_cents(buyer_before.get('balance_cents', 0)), _int_cents(get_balance(buyer_profile_id).get('balance_cents', 0)), _int_cents(buyer_before.get('pending_balance_cents', 0)), _int_cents(get_balance(buyer_profile_id).get('pending_balance_cents', 0)), reference_type=item_type, reference_id=item_id)
    _create_ledger_entry(seller_profile_id, None, credit.get('transaction_id'), 'marketplace_sale', net, _int_cents(seller_before.get('balance_cents', 0)), _int_cents(get_balance(seller_profile_id).get('balance_cents', 0)), _int_cents(seller_before.get('pending_balance_cents', 0)), _int_cents(get_balance(seller_profile_id).get('pending_balance_cents', 0)), reference_type=item_type, reference_id=item_id)
    if idempotency_key:
        _record_idempotency(idempotency_key, buyer_profile_id, 'marketplace_purchase')
    _notify(seller_profile_id, 'New Sale', 'Your ' + item_type + ' was purchased!', n_type='sale', entity_id=debit.get('transaction_id'), action_url='/wallet')
    return {'ok': True, 'transaction_id': debit.get('transaction_id'), 'amount_cents': val, 'fee_cents': fee, 'net_cents': net}


# ─── Refund ───

def refund_transaction(profile_id, original_transaction_id, reason='', idempotency_key=None):
    from services.wallet_service import get_wallet_transactions
    txs = get_wallet_transactions(profile_id, limit=1)
    original = None
    for tx in txs:
        if tx.get('id') == original_transaction_id or tx.get('reference_id') == original_transaction_id:
            original = tx
            break
    if not original:
        txs_all = safe_select('chain_wallet_transactions', limit=500, filters={'profile_id': profile_id})
        for tx in txs_all:
            tx_id = str(tx.get('id', ''))
            if tx_id == original_transaction_id:
                original = tx
                break
    if not original:
        return {'ok': False, 'error': 'Transaction not found'}
    original_amount = _int_cents(original.get('amount_cents', 0))
    if original_amount <= 0:
        return {'ok': False, 'error': 'Cannot refund zero or negative amount'}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, profile_id, 'refund')
        if existing:
            return {'ok': True, 'idempotent': True, 'transaction_id': existing.get('id')}
    from services.wallet_service import credit_wallet
    recipient = original.get('counterparty_profile_id') or original.get('source_profile_id') or profile_id
    result = credit_wallet(recipient, original_amount, description='Refund: ' + (reason or original.get('description', '')), transaction_type='refund', reference_type='refund', reference_id=original_transaction_id)
    if not result.get('ok'):
        return result
    _create_ledger_entry(recipient, None, result.get('transaction_id'), 'refund', original_amount, 0, 0, 0, 0, reference_type='refund', reference_id=original_transaction_id, description=reason)
    if idempotency_key:
        _record_idempotency(idempotency_key, profile_id, 'refund')
    _notify(recipient, 'Refund Processed', 'A refund of ' + str(original_amount) + ' coins was processed.', n_type='refund', entity_id=result.get('transaction_id'), action_url='/wallet')
    return {'ok': True, 'transaction_id': result.get('transaction_id'), 'amount_cents': original_amount}


# ─── Payout Methods ───

def add_payout_method(profile_id, provider, account_name, masked_account, country='NA', currency='NAD', is_default=False):
    valid_providers = ('bank', 'mobile_wallet', 'paypal', 'manual')
    if provider not in valid_providers:
        return {'ok': False, 'error': 'Invalid provider. Must be one of ' + str(valid_providers)}
    if is_default:
        safe_update('chain_payout_methods', {'is_default': False}, eq={'profile_id': profile_id})
    payload = {'profile_id': profile_id, 'provider': provider, 'account_name': account_name, 'masked_account': masked_account[:20], 'country': country, 'currency': currency, 'is_default': is_default, 'verification_status': 'unverified', 'created_at': _utcnow_iso(), 'updated_at': _utcnow_iso()}
    result = safe_insert('chain_payout_methods', payload)
    return {'ok': True, 'payout_method_id': result[0]["id"] if result else None}


def get_payout_methods(profile_id):
    return safe_select('chain_payout_methods', limit=20, filters={'profile_id': profile_id}, order_by='is_default', desc=True)


def delete_payout_method(profile_id, method_id):
    existing = safe_select('chain_payout_methods', limit=1, filters={'id': method_id, 'profile_id': profile_id}, order_by=None)
    if not existing:
        return {'ok': False, 'error': 'Payout method not found'}
    safe_delete('chain_payout_methods', eq={'id': method_id})
    return {'ok': True}


# ─── Payout Requests ───

def request_payout(profile_id, amount_cents, payout_method_id=None, notes=''):
    val_ok, val = validate_amount_cents(amount_cents)
    if not val_ok:
        return {'ok': False, 'error': val}
    balance = get_balance(profile_id)
    available = _int_cents(balance.get('withdrawable_balance_cents', 0)) or _int_cents(balance.get('balance_cents', 0))
    if val > available:
        return {'ok': False, 'error': 'Insufficient withdrawable balance'}
    from services.wallet_service import debit_wallet
    debit = debit_wallet(profile_id, val, description='Payout withdrawal', transaction_type='withdrawal')
    if not debit.get('ok'):
        return debit
    method_info = {}
    if payout_method_id:
        methods = safe_select('chain_payout_methods', limit=1, filters={'id': payout_method_id, 'profile_id': profile_id}, order_by=None)
        if methods:
            m = methods[0]
            method_info = {'provider': m.get('provider'), 'account_name': m.get('account_name'), 'masked_account': m.get('masked_account')}
    payout_payload = {'profile_id': profile_id, 'amount_cents': val, 'payout_method_id': payout_method_id, 'notes': notes, 'method_info': json.dumps(method_info), 'status': 'pending_review', 'created_at': _utcnow_iso()}
    payout_result = safe_insert('chain_payout_requests', payout_payload)
    _create_ledger_entry(profile_id, None, debit.get('transaction_id'), 'withdrawal', -val, 0, 0, 0, 0, reference_type='payout', description='Payout requested')
    _notify(profile_id, 'Payout Requested', 'Your payout of ' + str(val) + ' coins is pending review.', n_type='payout', entity_id=payout_result[0].get('id') if payout_result else None, action_url='/wallet')
    return {'ok': True, 'transaction_id': debit.get('transaction_id'), 'payout_id': payout_result[0].get('id') if payout_result else None, 'status': 'pending_review'}


# ─── Deposit (placeholder / test) ───

def deposit_wallet(profile_id, amount_cents, description='Deposit', idempotency_key=None):
    val_ok, val = validate_amount_cents(amount_cents)
    if not val_ok:
        return {'ok': False, 'error': val}
    if idempotency_key:
        existing = _check_idempotency(idempotency_key, profile_id, 'deposit')
        if existing:
            return {'ok': True, 'idempotent': True, 'transaction_id': existing.get('id')}
    from services.wallet_service import credit_wallet
    wallet_before = get_balance(profile_id)
    result = credit_wallet(profile_id, val, description=description, transaction_type='deposit')
    if not result.get('ok'):
        return result
    wallet_after = get_balance(profile_id)
    _create_ledger_entry(profile_id, None, result.get('transaction_id'), 'deposit', val, _int_cents(wallet_before.get('balance_cents', 0)), _int_cents(wallet_after.get('balance_cents', 0)), _int_cents(wallet_before.get('pending_balance_cents', 0)), _int_cents(wallet_after.get('pending_balance_cents', 0)), description=description)
    if idempotency_key:
        _record_idempotency(idempotency_key, profile_id, 'deposit')
    return {'ok': True, 'transaction_id': result.get('transaction_id'), 'amount_cents': val}
