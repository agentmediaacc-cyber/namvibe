from django.urls import path

from .views import (
    boost_post_view,
    boost_profile_view,
    boost_story_view,
    creator_earnings_view,
    membership_history_view,
    membership_overview_view,
    membership_plans_view,
    membership_purchase_view,
    send_gift_to_post_view,
    send_gift_to_story_view,
    send_gift_to_user_view,
    staff_wallet_control_view,
    wallet_coins_view,
    wallet_gifts_view,
    wallet_home_view,
    wallet_transactions_view,
)


urlpatterns = [
    path("", wallet_home_view, name="wallet_home"),
    path("coins/", wallet_coins_view, name="wallet_coins"),
    path("transactions/", wallet_transactions_view, name="wallet_transactions"),
    path("gifts/", wallet_gifts_view, name="wallet_gifts"),
    path("gifts/send/user/<str:username>/", send_gift_to_user_view, name="wallet_gift_user"),
    path("gifts/send/post/<uuid:uuid>/", send_gift_to_post_view, name="wallet_gift_post"),
    path("gifts/send/story/<int:id>/", send_gift_to_story_view, name="wallet_gift_story"),
    path("membership/", membership_overview_view, name="wallet_membership"),
    path("membership/plans/", membership_plans_view, name="wallet_membership_plans"),
    path("membership/history/", membership_history_view, name="wallet_membership_history"),
    path("membership/buy/<slug:slug>/", membership_purchase_view, name="wallet_membership_buy"),
    path("creator/earnings/", creator_earnings_view, name="wallet_creator_earnings"),
    path("boost/post/<uuid:uuid>/", boost_post_view, name="wallet_boost_post"),
    path("boost/profile/<str:username>/", boost_profile_view, name="wallet_boost_profile"),
    path("boost/story/<int:id>/", boost_story_view, name="wallet_boost_story"),
    path("staff/control/", staff_wallet_control_view, name="wallet_staff_control"),
]
