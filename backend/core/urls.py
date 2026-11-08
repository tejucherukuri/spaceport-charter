from django.urls import path

from .views import (
    create_booking,
    fleet_dashboard,
    health_check,
    list_ships,
    ship_unavailability,
)


urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("dashboard/", fleet_dashboard, name="fleet-dashboard"),
    path("ships/", list_ships, name="ship-list"),
    path(
        "ships/<int:ship_id>/unavailability/",
        ship_unavailability,
        name="ship-unavailability",
    ),
    path("bookings/", create_booking, name="booking-create"),
]
