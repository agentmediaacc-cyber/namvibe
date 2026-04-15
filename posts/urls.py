from django.urls import path
from .views import save_post_view

urlpatterns = [
    path('save/', save_post_view, name='save_post'),
]
