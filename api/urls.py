from django.urls import path
from .views import (
    api_root,
    dashboard_home,
    dashboard_users,
    dashboard_posts,
    dashboard_wallet,
    dashboard_support,
    dashboard_reports,
)

urlpatterns = [
    path('', api_root, name='api_root'),

    path('dashboard/', dashboard_home, name='dashboard_home'),
    path('dashboard/users/', dashboard_users, name='dashboard_users'),
    path('dashboard/posts/', dashboard_posts, name='dashboard_posts'),
    path('dashboard/wallet/', dashboard_wallet, name='dashboard_wallet'),
    path('dashboard/support/', dashboard_support, name='dashboard_support'),
    path('dashboard/reports/', dashboard_reports, name='dashboard_reports'),
]
