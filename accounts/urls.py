from django.urls import path

from .views import (
    account_gallery_view,
    forgot_password_view,
    login_view,
    logout_view,
    signup_view,
    user_dashboard_view,
    edit_profile_view,
    account_profile_detail,
    follow_toggle,
    profile_completion_view,
    profile_shortcut_view,
    verify_email_confirm_view,
    verify_email_notice_view,
    verify_email_request_view,
    resend_verification_email_view,
)

urlpatterns = [
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("signup/", signup_view, name="signup"),
    path("forgot-password/", forgot_password_view, name="forgot_password"),
    path("complete-profile/", profile_completion_view, name="profile_completion"),
    path("dashboard/", user_dashboard_view, name="user_dashboard"),

    path("profile/", profile_shortcut_view, name="profile_shortcut"),
    path("profile/gallery/", account_gallery_view, name="profile_gallery"),
    path("profile/edit/", edit_profile_view, name="profile_edit"),
    path("profile/<str:username>/", account_profile_detail, name="account_profile_detail"),
    path("profile/<str:username>/follow/", follow_toggle, name="follow_toggle"),

    path("verify-email/", verify_email_notice_view, name="verify_email_notice"),
    path("verify-email/request/", verify_email_request_view, name="verify_email_request"),
    path("verify-email/resend/", resend_verification_email_view, name="verify_email_resend"),
    path("verify-email/confirm/<str:token>/", verify_email_confirm_view, name="verify_email_confirm"),
]
