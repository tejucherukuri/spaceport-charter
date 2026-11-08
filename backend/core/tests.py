import io
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from django.db import IntegrityError, transaction
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone as django_timezone
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


class SeedImportTests(TestCase):
    def write_seed(self, payload):
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(payload, temp_file)
        temp_file.close()
        self.addCleanup(Path(temp_file.name).unlink, missing_ok=True)
        return temp_file.name

    def test_seed_loads_ships_and_offset_timestamps(self):
        seed_file = self.write_seed(
            {
                "ships": [{"id": 7, "name": "Serenity"}],
                "bookings": [
                    {
                        "shipId": 7,
                        "pilotName": "Malcolm Reynolds",
                        "startTime": "2026-11-09T08:00:00-06:00",
                        "endTime": "2026-11-09T09:00:00-06:00",
                    }
                ],
            }
        )

        call_command("load_seed", seed_file, stdout=io.StringIO())

        booking = Booking.objects.get()
        self.assertEqual(booking.ship.name, "Serenity")
        self.assertEqual(booking.pilot_name, "Malcolm Reynolds")
        self.assertEqual(booking.start_time.utcoffset(), timedelta(0))
        self.assertEqual(
            django_timezone.localtime(booking.start_time).isoformat(),
            "2026-11-09T08:00:00-06:00",
        )

    def test_invalid_seed_does_not_replace_existing_bookings(self):
        ship = Ship.objects.create(name="Existing")
        existing = Booking.objects.create(
            ship=ship,
            pilot_name="Existing pilot",
            start_time=datetime(2026, 11, 9, 15, tzinfo=timezone.utc),
            end_time=datetime(2026, 11, 9, 16, tzinfo=timezone.utc),
        )
        seed_file = self.write_seed(
            {
                "ships": [{"id": 8, "name": "New ship"}],
                "bookings": [
                    {
                        "shipId": 8,
                        "pilotName": "Pilot",
                        "startTime": "2026-11-09T08:00:00",
                        "endTime": "2026-11-09T09:00:00-06:00",
                    }
                ],
            }
        )

        with self.assertRaises(CommandError):
            call_command("load_seed", seed_file)

        self.assertEqual(list(Booking.objects.all()), [existing])
