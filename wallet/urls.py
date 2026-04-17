from django.urls import path

from .views import (
    creator_earnings_view,
    membership_history_view,
    membership_overview_view,
    membership_plans_view,
    membership_purchase_view,
    wallet_gifts_view,
    wallet_home_view,
    wallet_transactions_view,
)


urlpatterns = [
    path("", wallet_home_view, name="wallet_home"),
    path("transactions/", wallet_transactions_view, name="wallet_transactions"),
    path("gifts/", wallet_gifts_view, name="wallet_gifts"),
    path("membership/", membership_overview_view, name="wallet_membership"),
    path("membership/plans/", membership_plans_view, name="wallet_membership_plans"),
    path("membership/history/", membership_history_view, name="wallet_membership_history"),
    path("membership/buy/<slug:slug>/", membership_purchase_view, name="wallet_membership_buy"),
    path("creator/earnings/", creator_earnings_view, name="wallet_creator_earnings"),
]
