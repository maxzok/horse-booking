from django.urls import path
from . import views

app_name = "booking"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("calendar/events/", views.bookings_json, name="bookings_json"),
    path("booking/add/", views.booking_create, name="booking_create"),
    path("booking/<int:pk>/edit/", views.booking_edit, name="booking_edit"),
    path("booking/<int:pk>/complete/", views.complete_booking, name="complete_booking"),
    path("client/<int:pk>/", views.client_detail, name="client_detail"),
    path("api/available-slots/", views.get_available_slots, name="available_slots"),
    path("clients/", views.client_list, name="client_list"),
    path("trainer/<int:pk>/stats/", views.trainer_stats, name="trainer_stats"),
    path("horse/<int:pk>/stats/", views.horse_stats, name="horse_stats"),
    path(
        "subscriptions/active/", views.active_subscriptions, name="active_subscriptions"
    ),
    path(
        "subscription/<int:pk>/", views.subscription_detail, name="subscription_detail"
    ),
]
