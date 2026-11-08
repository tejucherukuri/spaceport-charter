from django.urls import path

from .views import create_booking, health_check, list_ships


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("ships/", list_ships, name="ship-list"),
    path("bookings/", create_booking, name="booking-create"),
]
