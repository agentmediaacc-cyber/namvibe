from django.urls import path
from .views import login_view, logout_view, signup_view, forgot_password_view, user_dashboard_view

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('signup/', signup_view, name='signup'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('dashboard/', user_dashboard_view, name='user_dashboard'),
]
