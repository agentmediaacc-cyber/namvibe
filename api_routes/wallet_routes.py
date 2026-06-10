import json
import os

from flask import Blueprint, jsonify, request, session, render_template
from api_routes.profile_routes import login_required
from services.profile_service import get_current_profile, get_lightweight_profile
from services.wallet_service import (
    get_wallet,
    get_wallet_transactions,
    get_wallet_summary,
    get_or_create_wallet,
    credit_wallet,
    debit_wallet,
)
from services.creator_monetization_service import (
    send_tip,
    send_gift,
    get_available_gifts,
    subscribe_to_creator,
    cancel_creator_subscription,
    create_paid_content,
    purchase_paid_content,
    get_creator_dashboard,
    get_creator_earnings,
)
from services.payout_service import (
    request_payout,
    get_payout_requests,
    get_creator_payouts,
    approve_payout,
    reject_payout,
    mark_payout_paid,
)
from services.wallet_payment_service import (
    get_balance_summary,
    list_transactions,
    get_earnings_breakdown,
    send_tip as premium_send_tip,
    send_gift as premium_send_gift,
    pay_subscription,
    marketplace_purchase,
    refund_transaction,
    request_payout as premium_request_payout,
    add_payout_method,
    get_payout_methods,
    delete_payout_method,
    deposit_wallet,
    get_balance,
)

wallet_bp = Blueprint('wallet', __name__, url_prefix='/wallet')


# ---------- WALLET MANAGEMENT ----------

@wallet_bp.route('/api/balance', methods=['GET'])
@login_required
def api_balance():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    wallet = get_wallet(profile_id)
    if not wallet:
        wallet = get_or_create_wallet(profile_id)
    if not wallet:
        return jsonify({'ok': False, 'error': 'wallet_not_found'}), 404
    return jsonify({'ok': True, 'wallet': wallet})


@wallet_bp.route('/api/transactions', methods=['GET'])
@login_required
def api_transactions():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    tx_type = request.args.get('type')
    txs = get_wallet_transactions(profile_id, limit=limit, offset=offset, transaction_type=tx_type)
    return jsonify({'ok': True, 'transactions': txs})


@wallet_bp.route('/api/summary', methods=['GET'])
@login_required
def api_summary():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    summary = get_wallet_summary(profile_id)
    if not summary:
        return jsonify({'ok': False, 'error': 'wallet_not_found'}), 404
    return jsonify({'ok': True, 'summary': summary})


# ---------- TIPS ----------

@wallet_bp.route('/api/tip', methods=['POST'])
@login_required
def api_tip():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    receiver_id = data.get('receiver_profile_id')
    amount_cents = int(float(data.get('amount_cents', 0)))
    message = data.get('message', '')
    idempotency_key = data.get('idempotency_key')
    if not receiver_id:
        return jsonify({'ok': False, 'error': 'receiver_required'}), 400
    if amount_cents <= 0:
        return jsonify({'ok': False, 'error': 'invalid_amount'}), 400
    result = premium_send_tip(profile_id, receiver_id, amount_cents, message=message, idempotency_key=idempotency_key)
    if result.get('ok'):
        return jsonify({'ok': True, 'transaction_id': result.get('transaction_id'), 'amount_cents': amount_cents, 'fee_cents': result.get('fee_cents', 0), 'net_cents': result.get('net_cents', amount_cents)}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'tip_failed')}), 400


# ---------- GIFTS ----------

@wallet_bp.route('/api/gifts', methods=['GET'])
def api_gifts():
    gifts = get_available_gifts()
    return jsonify({'ok': True, 'gifts': gifts})


@wallet_bp.route('/api/gift', methods=['POST'])
@login_required
def api_gift():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    receiver_id = data.get('receiver_profile_id')
    gift_id = data.get('gift_id')
    idempotency_key = data.get('idempotency_key')
    if not receiver_id or not gift_id:
        return jsonify({'ok': False, 'error': 'receiver_and_gift_required'}), 400
    result = premium_send_gift(profile_id, receiver_id, gift_id, idempotency_key=idempotency_key)
    if result.get('ok'):
        return jsonify({
            'ok': True,
            'transaction_id': result.get('transaction_id'),
            'gift': result.get('gift'),
            'amount_cents': result.get('amount_cents'),
            'fee_cents': result.get('fee_cents', 0),
            'net_cents': result.get('net_cents', 0),
        }), 200
    return jsonify({'ok': False, 'error': result.get('error', 'gift_failed')}), 400


# ---------- SUBSCRIPTIONS ----------

@wallet_bp.route('/api/subscribe', methods=['POST'])
@login_required
def api_subscribe():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    creator_id = data.get('creator_profile_id')
    tier = data.get('tier_name', 'basic')
    price_cents = int(float(data.get('price_cents', 0)))
    idempotency_key = data.get('idempotency_key')
    if not creator_id:
        return jsonify({'ok': False, 'error': 'creator_required'}), 400
    result = pay_subscription(profile_id, creator_id, price_cents, tier=tier, idempotency_key=idempotency_key)
    if result.get('ok'):
        return jsonify({'ok': True, 'subscription_id': result.get('transaction_id'), 'amount_cents': result.get('amount_cents'), 'fee_cents': result.get('fee_cents', 0)}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'subscribe_failed')}), 400


@wallet_bp.route('/api/unsubscribe', methods=['POST'])
@login_required
def api_unsubscribe():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    creator_id = data.get('creator_profile_id')
    if not creator_id:
        return jsonify({'ok': False, 'error': 'creator_required'}), 400
    result = cancel_creator_subscription(profile_id, creator_id)
    if result.get('ok'):
        return jsonify({'ok': True}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'unsubscribe_failed')}), 400


# ---------- CREATOR DASHBOARD ----------

@wallet_bp.route('/api/creator/<profile_id>/dashboard', methods=['GET'])
def api_creator_dashboard(profile_id):
    dashboard = get_creator_dashboard(profile_id)
    if not dashboard:
        return jsonify({'ok': False, 'error': 'creator_not_found'}), 404
    return jsonify({'ok': True, 'dashboard': dashboard})


# ---------- PAID CONTENT ----------

@wallet_bp.route('/api/paid-content', methods=['POST'])
@login_required
def api_create_paid_content():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    content_type = data.get('content_type', 'post')
    price_cents = int(float(data.get('price_cents', 0)))
    content_id = data.get('content_id')
    result = create_paid_content(profile_id, content_type, price_cents, content_id=content_id)
    if result.get('ok'):
        return jsonify({'ok': True, 'paid_content_id': result.get('paid_content_id')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'create_failed')}), 400


@wallet_bp.route('/api/purchase-content', methods=['POST'])
@login_required
def api_purchase_content():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    creator_id = data.get('creator_profile_id')
    paid_content_id = data.get('paid_content_id')
    if not creator_id or not paid_content_id:
        return jsonify({'ok': False, 'error': 'creator_and_content_required'}), 400
    result = purchase_paid_content(profile_id, creator_id, paid_content_id)
    if result.get('ok'):
        return jsonify({'ok': True, 'transaction_id': result.get('transaction_id')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'purchase_failed')}), 400


# ---------- PAYOUTS ----------

@wallet_bp.route('/api/payouts', methods=['GET'])
@login_required
def api_payouts():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    payouts = get_creator_payouts(profile_id, limit=limit, offset=offset)
    return jsonify({'ok': True, 'payouts': payouts})


@wallet_bp.route('/api/payouts/request', methods=['POST'])
@login_required
def api_request_payout():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    amount_cents = int(float(data.get('amount_cents', 0)))
    payout_method_id = data.get('payout_method_id')
    notes = data.get('notes', '')
    if amount_cents <= 0:
        return jsonify({'ok': False, 'error': 'invalid_amount'}), 400
    result = premium_request_payout(profile_id, amount_cents, payout_method_id=payout_method_id, notes=notes)
    if result.get('ok'):
        return jsonify({'ok': True, 'payout_id': result.get('payout_id'), 'status': result.get('status')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'payout_failed')}), 400


# ---------- ADMIN PAYOUT REVIEW ----------

@wallet_bp.route('/admin/api/payouts', methods=['GET'])
@login_required
def admin_get_payouts():
    status_filter = request.args.get('status')
    limit = request.args.get('limit', 50, type=int)
    offset = request.args.get('offset', 0, type=int)
    payouts = get_payout_requests(status=status_filter, limit=limit, offset=offset)
    return jsonify({'ok': True, 'payouts': payouts})


@wallet_bp.route('/admin/api/payouts/<payout_id>/approve', methods=['POST'])
@login_required
def admin_approve_payout(payout_id):
    data = request.get_json(silent=True) or request.form.to_dict()
    note = data.get('admin_note')
    result = approve_payout(payout_id, admin_note=note)
    if result.get('ok'):
        return jsonify({'ok': True, 'status': result.get('status')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'approve_failed')}), 400


@wallet_bp.route('/admin/api/payouts/<payout_id>/reject', methods=['POST'])
@login_required
def admin_reject_payout(payout_id):
    data = request.get_json(silent=True) or request.form.to_dict()
    note = data.get('admin_note')
    result = reject_payout(payout_id, admin_note=note)
    if result.get('ok'):
        return jsonify({'ok': True, 'status': result.get('status')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'reject_failed')}), 400


@wallet_bp.route('/admin/api/payouts/<payout_id>/mark-paid', methods=['POST'])
@login_required
def admin_mark_payout_paid(payout_id):
    result = mark_payout_paid(payout_id)
    if result.get('ok'):
        return jsonify({'ok': True, 'status': result.get('status')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'mark_paid_failed')}), 400


# ---------- PREMIUM WALLET API ROUTES ----------

@wallet_bp.route('/api/wallet/balance-summary', methods=['GET'])
@login_required
def api_balance_summary():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    summary = get_balance_summary(profile_id)
    return jsonify({'ok': True, 'summary': summary})


@wallet_bp.route('/api/wallet/earnings-breakdown', methods=['GET'])
@login_required
def api_earnings_breakdown():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    breakdown = get_earnings_breakdown(profile_id)
    return jsonify({'ok': True, 'breakdown': breakdown})


@wallet_bp.route('/api/wallet/purchase', methods=['POST'])
@login_required
def api_purchase():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    seller_id = data.get('seller_profile_id')
    amount_cents = int(float(data.get('amount_cents', 0)))
    item_id = data.get('item_id')
    item_type = data.get('item_type', 'product')
    idempotency_key = data.get('idempotency_key')
    if not seller_id or amount_cents <= 0:
        return jsonify({'ok': False, 'error': 'seller_and_amount_required'}), 400
    result = marketplace_purchase(profile_id, seller_id, amount_cents, item_id=item_id, item_type=item_type, idempotency_key=idempotency_key)
    if result.get('ok'):
        return jsonify({'ok': True, 'transaction_id': result.get('transaction_id'), 'amount_cents': result.get('amount_cents'), 'fee_cents': result.get('fee_cents', 0), 'net_cents': result.get('net_cents', 0)}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'purchase_failed')}), 400


@wallet_bp.route('/api/wallet/refund', methods=['POST'])
@login_required
def api_refund():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    tx_id = data.get('transaction_id')
    reason = data.get('reason', '')
    idempotency_key = data.get('idempotency_key')
    if not tx_id:
        return jsonify({'ok': False, 'error': 'transaction_id_required'}), 400
    result = refund_transaction(profile_id, tx_id, reason=reason, idempotency_key=idempotency_key)
    if result.get('ok'):
        return jsonify({'ok': True, 'transaction_id': result.get('transaction_id'), 'amount_cents': result.get('amount_cents')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'refund_failed')}), 400


@wallet_bp.route('/api/wallet/payout-methods', methods=['GET'])
@login_required
def api_get_payout_methods():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    methods = get_payout_methods(profile_id)
    return jsonify({'ok': True, 'payout_methods': methods})


@wallet_bp.route('/api/wallet/payout-methods', methods=['POST'])
@login_required
def api_add_payout_method():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    provider = data.get('provider')
    account_name = data.get('account_name', '').strip()
    masked_account = data.get('masked_account', '').strip()
    country = data.get('country', 'NA')
    currency = data.get('currency', 'NAD')
    is_default = data.get('is_default', False)
    if not provider or not account_name:
        return jsonify({'ok': False, 'error': 'provider_and_account_name_required'}), 400
    result = add_payout_method(profile_id, provider, account_name, masked_account, country=country, currency=currency, is_default=is_default)
    if result.get('ok'):
        return jsonify({'ok': True, 'payout_method_id': result.get('payout_method_id')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'add_failed')}), 400


@wallet_bp.route('/api/wallet/payout-methods/<method_id>', methods=['DELETE'])
@login_required
def api_delete_payout_method(method_id):
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    result = delete_payout_method(profile_id, method_id)
    if result.get('ok'):
        return jsonify({'ok': True}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'delete_failed')}), 400


@wallet_bp.route('/api/wallet/deposit', methods=['POST'])
@login_required
def api_deposit():
    profile_id = session.get('profile_id')
    if not profile_id:
        return jsonify({'ok': False, 'error': 'unauthorized'}), 401
    data = request.get_json(silent=True) or request.form.to_dict()
    amount_cents = int(float(data.get('amount_cents', 0)))
    idempotency_key = data.get('idempotency_key')
    if amount_cents <= 0:
        return jsonify({'ok': False, 'error': 'invalid_amount'}), 400
    result = deposit_wallet(profile_id, amount_cents, idempotency_key=idempotency_key)
    if result.get('ok'):
        return jsonify({'ok': True, 'transaction_id': result.get('transaction_id'), 'amount_cents': result.get('amount_cents')}), 200
    return jsonify({'ok': False, 'error': result.get('error', 'deposit_failed')}), 400


# ---------- HTML PAGES ----------

@wallet_bp.route('/')
@login_required
def index():
    profile = get_current_profile()
    if not profile or not profile.get('id'):
        return render_template('wallet/dashboard.html', profile={'id': None, 'username': 'guest'}, wallet=None, error='Login required')
    wallet = get_wallet(profile['id'])
    if not wallet:
        wallet = get_or_create_wallet(profile['id'])
    txs = get_wallet_transactions(profile['id'], limit=20)
    summary = get_balance_summary(profile['id'])
    breakdown = get_earnings_breakdown(profile['id'])
    payout_methods = get_payout_methods(profile['id'])
    return render_template('wallet/index.html', profile=profile, wallet=wallet, transactions=txs, summary=summary, breakdown=breakdown, payout_methods=payout_methods)


@wallet_bp.route('/transactions')
@login_required
def transactions_page():
    profile = get_current_profile()
    if not profile or not profile.get('id'):
        return render_template('wallet/transactions.html', profile={'id': None, 'username': 'guest'}, transactions=[])
    txs = get_wallet_transactions(profile['id'], limit=100)
    return render_template('wallet/transactions.html', profile=profile, transactions=txs)


@wallet_bp.route('/creator/<creator_id>/earnings')
@login_required
def creator_earnings_page(creator_id):
    profile = get_current_profile()
    dashboard = get_creator_dashboard(creator_id)
    return render_template('wallet/creator_earnings.html', profile=profile, creator_id=creator_id, dashboard=dashboard)


@wallet_bp.route('/payouts')
@login_required
def payouts_page():
    profile = get_current_profile()
    if not profile or not profile.get('id'):
        return render_template('wallet/payouts.html', profile={'id': None, 'username': 'guest'}, payouts=[])
    payouts = get_creator_payouts(profile['id'], limit=50)
    wallet = get_wallet(profile['id'])
    return render_template('wallet/payouts.html', profile=profile, payouts=payouts, wallet=wallet)
