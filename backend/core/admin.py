from django.contrib import admin

from .models import Booking, Ship


@admin.register(Ship)
class ShipAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    search_fields = ["name"]


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ["id", "ship", "pilot_name", "start_time", "end_time"]
    list_filter = ["ship"]
    search_fields = ["pilot_name"]
    ordering = ["start_time"]
