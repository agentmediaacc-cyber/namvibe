from django.urls import path
from .views import (
    edit_profile_view,
    follow_toggle_view,
    forgot_password_view,
    login_view,
    logout_view,
    public_profile_view,
    profile_completion_view,
    signup_view,
    user_dashboard_view,
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup_view, name='signup'),
    path('complete-profile/', profile_completion_view, name='profile_completion'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('dashboard/', user_dashboard_view, name='user_dashboard'),
    path('profile/edit/', edit_profile_view, name='profile_edit'),
    path('profile/<str:username>/', public_profile_view, name='account_profile_detail'),
    path('profile/<str:username>/follow/', follow_toggle_view, name='follow_toggle'),
]
