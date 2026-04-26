from django.urls import path
from . import views

app_name = "ehealth"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("card/", views.card, name="card"),
    path("appointments/", views.appointments, name="appointments"),
    path("messages/", views.messages, name="messages"),
    path("consent/", views.consent, name="consent"),
]
