from datetime import datetime, timezone

from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from rest_framework.test import APITestCase

from .models import Booking, Ship


class HealthCheckTests(APITestCase):
    def test_health_endpoint_returns_ok(self):
        response = self.client.get("/api/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})


class BookingModelTests(TestCase):
    def setUp(self):
        self.ship = Ship.objects.create(name="USS Wanderer")

    def test_booking_belongs_to_ship(self):
        booking = Booking.objects.create(
            ship=self.ship,
            pilot_name="Han Solo",
            start_time=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 11, 9, 16, tzinfo=timezone.utc),
        )

        self.assertEqual(booking.ship, self.ship)
        self.assertEqual(self.ship.bookings.get(), booking)

    def test_end_must_be_after_start_at_database_level(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Booking.objects.create(
                ship=self.ship,
                pilot_name="Han Solo",
                start_time=datetime(2026, 11, 9, 16, tzinfo=timezone.utc),
                end_time=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
            )

    def test_ship_with_bookings_cannot_be_deleted(self):
        Booking.objects.create(
            ship=self.ship,
            pilot_name="Han Solo",
            start_time=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 11, 9, 16, tzinfo=timezone.utc),
        )

        with self.assertRaises(ProtectedError):
            self.ship.delete()
