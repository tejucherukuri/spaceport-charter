import io
import json
import tempfile
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db import IntegrityError, transaction
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.utils import timezone as django_timezone
from rest_framework.test import APITestCase

from .services import (
    BookingConflictError,
    BookingRuleError,
    validate_booking,
    validate_booking_times,
)
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


class BookingRuleTests(TestCase):
    central = ZoneInfo("America/Chicago")

    def setUp(self):
        self.ship = Ship.objects.create(name="Rocinante")
        self.day = date(2026, 11, 9)

    def local(self, hour, minute=0, day=None):
        return datetime.combine(day or self.day, time(hour, minute), tzinfo=self.central)

    def add_booking(self, start, end, ship=None):
        return Booking.objects.create(
            ship=ship or self.ship,
            pilot_name="James Holden",
            start_time=start,
            end_time=end,
        )

    def test_booking_within_operating_hours_is_valid(self):
        start, end = validate_booking_times(
            self.local(6), self.local(22)
        )

        self.assertEqual(start.astimezone(self.central).time(), time(6))
        self.assertEqual(end.astimezone(self.central).time(), time(22))

    def test_booking_outside_operating_hours_is_rejected(self):
        with self.assertRaisesRegex(BookingRuleError, "6:00 AM"):
            validate_booking_times(self.local(5, 59), self.local(7))
        with self.assertRaisesRegex(BookingRuleError, "6:00 AM"):
            validate_booking_times(self.local(21), self.local(22, 1))

    def test_end_must_follow_start_and_stay_on_same_central_date(self):
        with self.assertRaisesRegex(BookingRuleError, "after"):
            validate_booking_times(self.local(10), self.local(10))
        with self.assertRaisesRegex(BookingRuleError, "after"):
            validate_booking_times(self.local(11), self.local(10))
        with self.assertRaisesRegex(BookingRuleError, "same Central Time date"):
            validate_booking_times(self.local(21), self.local(6, day=date(2026, 11, 10)))

    def test_naive_timestamps_are_rejected(self):
        with self.assertRaisesRegex(BookingRuleError, "include a timezone"):
            validate_booking_times(
                datetime(2026, 11, 9, 10),
                datetime(2026, 11, 9, 11),
            )

    def test_dst_operating_window_uses_central_offset_for_that_date(self):
        spring_open = datetime(2026, 3, 8, 6, tzinfo=self.central)
        fall_open = datetime(2026, 11, 1, 6, tzinfo=self.central)

        spring_start, _ = validate_booking_times(
            spring_open, datetime(2026, 3, 8, 7, tzinfo=self.central)
        )
        fall_start, _ = validate_booking_times(
            fall_open, datetime(2026, 11, 1, 7, tzinfo=self.central)
        )

        self.assertEqual(spring_start.utcoffset(), timedelta(0))
        self.assertEqual(spring_start.hour, 11)
        self.assertEqual(fall_start.utcoffset(), timedelta(0))
        self.assertEqual(fall_start.hour, 12)

    def test_overlapping_booking_on_same_ship_is_rejected(self):
        self.add_booking(self.local(10), self.local(12))

        with self.assertRaises(BookingConflictError):
            validate_booking(self.ship.id, self.local(11), self.local(13))

    def test_refueling_buffer_is_enforced_before_and_after(self):
        self.add_booking(self.local(10), self.local(12))

        with self.assertRaises(BookingConflictError):
            validate_booking(self.ship.id, self.local(12, 29), self.local(13))
        with self.assertRaises(BookingConflictError):
            validate_booking(self.ship.id, self.local(9), self.local(9, 31))

    def test_exactly_thirty_minutes_of_refueling_is_allowed(self):
        self.add_booking(self.local(10), self.local(12))

        validate_booking(self.ship.id, self.local(12, 30), self.local(13))
        validate_booking(self.ship.id, self.local(9), self.local(9, 30))

    def test_different_ship_can_book_same_time(self):
        other_ship = Ship.objects.create(name="Serenity")
        self.add_booking(self.local(10), self.local(12))

        start, end = validate_booking(other_ship.id, self.local(10), self.local(12))

        self.assertEqual(start.astimezone(self.central).time(), time(10))
        self.assertEqual(end.astimezone(self.central).time(), time(12))
