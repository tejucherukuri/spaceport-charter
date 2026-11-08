import io
import json
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from threading import Barrier
from zoneinfo import ZoneInfo

from django.db import close_old_connections
from django.db import IntegrityError, transaction
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.deletion import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone as django_timezone
from rest_framework.test import APIClient, APITestCase

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


class BookingApiTests(APITestCase):
    def setUp(self):
        self.ship = Ship.objects.create(name="USS Wanderer")
        self.other_ship = Ship.objects.create(name="Nostromo")

    def payload(self, start, end, ship_id=None, pilot="Han Solo"):
        return {
            "shipId": ship_id or self.ship.id,
            "pilotName": pilot,
            "startTime": f"2030-07-10T{start}-05:00",
            "endTime": f"2030-07-10T{end}-05:00",
        }

    def create(self, start, end, ship_id=None, pilot="Han Solo"):
        return self.client.post(
            "/api/bookings/",
            self.payload(start, end, ship_id, pilot),
            format="json",
        )

    def test_list_ships_returns_fleet(self):
        response = self.client.get("/api/ships/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {"id": self.ship.id, "name": "USS Wanderer"},
                {"id": self.other_ship.id, "name": "Nostromo"},
            ],
        )

    def test_create_booking_returns_central_iso_timestamps(self):
        response = self.create("10:00:00", "11:00:00")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["shipId"], self.ship.id)
        self.assertEqual(response.json()["pilotName"], "Han Solo")
        self.assertTrue(response.json()["startTime"].endswith("-05:00"))
        self.assertEqual(Booking.objects.count(), 1)

    def test_overlapping_booking_returns_conflict(self):
        self.assertEqual(self.create("10:00:00", "12:00:00").status_code, 201)

        response = self.create("11:00:00", "13:00:00")

        self.assertEqual(response.status_code, 409)
        self.assertIn("unavailable", response.json()["detail"])
        self.assertEqual(Booking.objects.count(), 1)

    def test_refueling_buffer_and_exact_boundary(self):
        self.assertEqual(self.create("10:00:00", "12:00:00").status_code, 201)
        self.assertEqual(self.create("12:29:00", "13:00:00").status_code, 409)
        self.assertEqual(self.create("12:30:00", "13:00:00").status_code, 201)

    def test_booking_before_existing_booking_obeys_buffer(self):
        self.assertEqual(self.create("10:00:00", "12:00:00").status_code, 201)

        self.assertEqual(self.create("09:30:00", "09:59:00").status_code, 409)
        self.assertEqual(self.create("09:00:00", "09:30:00").status_code, 201)

    def test_different_ship_can_book_same_time(self):
        self.assertEqual(self.create("10:00:00", "12:00:00").status_code, 201)

        response = self.create("10:00:00", "12:00:00", self.other_ship.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(Booking.objects.count(), 2)

    def test_outside_hours_and_invalid_order_return_422(self):
        outside = self.create("05:00:00", "06:00:00")
        reversed_times = self.create("11:00:00", "10:00:00")

        self.assertEqual(outside.status_code, 422)
        self.assertIn("6:00 AM", outside.json()["detail"])
        self.assertEqual(reversed_times.status_code, 422)

    def test_missing_pilot_and_timezone_are_validation_errors(self):
        missing_pilot = self.client.post(
            "/api/bookings/",
            self.payload("10:00:00", "11:00:00", pilot="  "),
            format="json",
        )
        naive_timestamp = self.payload("10:00:00", "11:00:00")
        naive_timestamp["startTime"] = "2030-07-10T10:00:00"
        invalid_timestamp = self.client.post(
            "/api/bookings/",
            naive_timestamp,
            format="json",
        )

        self.assertEqual(missing_pilot.status_code, 400)
        self.assertEqual(invalid_timestamp.status_code, 400)
        self.assertIn("timezone offset", str(invalid_timestamp.json()))

    def test_malformed_timestamp_returns_validation_error(self):
        payload = self.payload("10:00:00", "11:00:00")
        payload["startTime"] = "not-a-date-05:00"

        response = self.client.post("/api/bookings/", payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("startTime", response.json())

    def test_unknown_ship_returns_404(self):
        response = self.create("10:00:00", "11:00:00", ship_id=999)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Ship not found."})


class ConcurrentBookingApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.ship = Ship.objects.create(name="Millennium Falcon")

    def test_only_one_concurrent_request_can_book_the_same_slot(self):
        barrier = Barrier(2)
        payload = {
            "shipId": self.ship.id,
            "pilotName": "Leia Organa",
            "startTime": "2030-07-10T10:00:00-05:00",
            "endTime": "2030-07-10T11:00:00-05:00",
        }

        def submit_booking():
            close_old_connections()
            try:
                barrier.wait(timeout=5)
                client = APIClient()
                response = client.post("/api/bookings/", payload, format="json")
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit_booking(), range(2)))

        self.assertCountEqual(results, [201, 409])
        self.assertEqual(Booking.objects.filter(ship=self.ship).count(), 1)


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
