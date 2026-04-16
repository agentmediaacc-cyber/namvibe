from django.urls import path
from .views import live_studio_view

urlpatterns = [
    path('studio/', live_studio_view, name='legacy_live_studio'),
]
