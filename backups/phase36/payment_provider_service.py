import os
import logging

logger = logging.getLogger(__name__)

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
PAYPAL_CLIENT_ID = os.environ.get("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.environ.get("PAYPAL_CLIENT_SECRET", "")
PAYPAL_MODE = os.environ.get("PAYPAL_MODE", "sandbox")


def _detect_providers():
    providers = []
    if STRIPE_SECRET_KEY:
        providers.append("stripe")
    if PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET:
        providers.append("paypal")
    return providers


def payment_configured():
    return bool(_detect_providers())


def get_payment_providers():
    return _detect_providers()


def get_payment_status():
    providers = _detect_providers()
    if not providers:
        return {
            "status": "provider_required",
            "detail": "No payment provider configured. Set STRIPE_SECRET_KEY or PAYPAL_CLIENT_ID + PAYPAL_CLIENT_SECRET.",
            "providers": [],
            "capabilities": {
                "subscriptions": False,
                "paid_posts": False,
                "premium_content": False,
                "tips": False,
                "gifts": False,
                "wallet_topup": False,
                "payouts": False,
            },
        }
    caps = {
        "subscriptions": "stripe" in providers,
        "paid_posts": "stripe" in providers,
        "premium_content": "stripe" in providers,
        "tips": bool(providers),
        "gifts": bool(providers),
        "wallet_topup": bool(providers),
        "payouts": "stripe" in providers,
    }
    return {
        "status": "ready",
        "providers": providers,
        "capabilities": caps,
    }


def create_subscription_checkout(profile_id, plan_id, success_url, cancel_url):
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe not configured", "provider_required": True}
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": plan_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"profile_id": profile_id},
        )
        return {"url": session.url, "session_id": session.id}
    except ImportError:
        return {"error": "stripe module not installed", "provider_required": True}
    except Exception as e:
        return {"error": str(e)}


def create_payment_intent(amount_coins, currency="usd", metadata=None):
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe not configured", "provider_required": True}
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.create(
            amount=int(amount_coins * 100),
            currency=currency,
            metadata=metadata or {},
        )
        return {"client_secret": intent.client_secret, "intent_id": intent.id}
    except ImportError:
        return {"error": "stripe module not installed", "provider_required": True}
    except Exception as e:
        return {"error": str(e)}


def create_payout(profile_id, amount_coins, destination):
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe not configured", "provider_required": True}
    try:
        import stripe
        stripe.api_key = STRIPE_SECRET_KEY
        payout = stripe.Payout.create(
            amount=int(amount_coins * 100),
            currency="usd",
            destination=destination,
            metadata={"profile_id": profile_id},
        )
        return {"payout_id": payout.id, "status": payout.status}
    except ImportError:
        return {"error": "stripe module not installed", "provider_required": True}
    except Exception as e:
        return {"error": str(e)}
