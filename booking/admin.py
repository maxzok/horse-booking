from django.contrib import admin
from .models import (
    Client,
    Trainer,
    Horse,
    ServiceType,
    Subscription,
    ClientSubscription,
    Booking,
)


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "phone", "riding_level", "is_active")
    search_fields = ("first_name", "last_name", "phone")


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "user", "is_active")
    list_filter = ("is_active",)


@admin.register(Horse)
class HorseAdmin(admin.ModelAdmin):
    list_display = ("name", "breed", "level", "is_active")
    list_filter = ("level", "is_active")


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "duration", "default_price")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "service_type",
        "visits",
        "price",
        "validity_days",
        "is_active",
    )


@admin.register(ClientSubscription)
class ClientSubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        "client",
        "subscription",
        "remaining_visits",
        "start_date",
        "end_date",
    )


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("client", "trainer", "horse", "start_time", "status")
    list_filter = ("status", "trainer", "horse")
