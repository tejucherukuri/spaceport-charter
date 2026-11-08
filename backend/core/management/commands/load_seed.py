import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Booking, Ship


class Command(BaseCommand):
    help = "Load the Spaceport seed JSON, replacing the existing fleet and bookings."

    def add_arguments(self, parser):
        parser.add_argument(
            "seed_file",
            nargs="?",
            type=Path,
            default=settings.BASE_DIR.parent / "seed.json",
            help="Path to seed JSON (defaults to seed.json beside the backend directory).",
        )

    def handle(self, *args, **options):
        seed_path = options["seed_file"]
        try:
            with seed_path.open(encoding="utf-8") as seed_file:
                payload = json.load(seed_file)
        except OSError as exc:
            raise CommandError(f"Cannot read seed file {seed_path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"Invalid JSON in {seed_path}: {exc}") from exc

        ships, bookings = self.parse_seed(payload)

        with transaction.atomic():
            for ship in ships:
                Ship.objects.update_or_create(
                    id=ship["id"],
                    defaults={"name": ship["name"]},
                )

            Booking.objects.all().delete()
            Booking.objects.bulk_create(bookings, batch_size=500)

            ship_ids = [ship["id"] for ship in ships]
            Ship.objects.exclude(id__in=ship_ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Loaded {len(ships)} ships and {len(bookings)} bookings from {seed_path}."
            )
        )

    def parse_seed(self, payload):
        if not isinstance(payload, dict):
            raise CommandError("Seed must be a JSON object with 'ships' and 'bookings'.")
        raw_ships, raw_bookings = payload.get("ships"), payload.get("bookings")
        if not isinstance(raw_ships, list) or not isinstance(raw_bookings, list):
            raise CommandError("'ships' and 'bookings' must both be JSON arrays.")
        if not raw_ships:
            raise CommandError("Seed must contain at least one ship.")

        ships = []
        ship_ids = set()
        for index, item in enumerate(raw_ships):
            if not isinstance(item, dict):
                raise CommandError(f"ships[{index}] must be an object.")
            ship_id, name = item.get("id"), item.get("name")
            if not isinstance(ship_id, int) or isinstance(ship_id, bool) or ship_id <= 0:
                raise CommandError(f"ships[{index}].id must be a positive integer.")
            if ship_id in ship_ids:
                raise CommandError(f"Duplicate ship id {ship_id} in seed.")
            if not isinstance(name, str) or not name.strip():
                raise CommandError(f"ships[{index}].name must be a non-empty string.")
            ships.append({"id": ship_id, "name": name.strip()})
            ship_ids.add(ship_id)

        bookings = []
        for index, item in enumerate(raw_bookings):
            if not isinstance(item, dict):
                raise CommandError(f"bookings[{index}] must be an object.")
            ship_id = item.get("shipId")
            pilot_name = item.get("pilotName")
            if not isinstance(ship_id, int) or isinstance(ship_id, bool) or ship_id not in ship_ids:
                raise CommandError(f"bookings[{index}].shipId must reference a seeded ship.")
            if not isinstance(pilot_name, str) or not pilot_name.strip():
                raise CommandError(f"bookings[{index}].pilotName must be non-empty.")

            start = self.parse_timestamp(item.get("startTime"), index, "startTime")
            end = self.parse_timestamp(item.get("endTime"), index, "endTime")
            if end <= start:
                raise CommandError(f"bookings[{index}].endTime must be after startTime.")

            bookings.append(
                Booking(
                    ship_id=ship_id,
                    pilot_name=pilot_name.strip(),
                    start_time=start,
                    end_time=end,
                )
            )

        return ships, bookings

    @staticmethod
    def parse_timestamp(value, index, field):
        if not isinstance(value, str):
            raise CommandError(f"bookings[{index}].{field} must be an ISO 8601 string.")
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as exc:
            raise CommandError(
                f"bookings[{index}].{field} is not a valid ISO 8601 timestamp."
            ) from exc
        if timezone.is_naive(parsed):
            raise CommandError(
                f"bookings[{index}].{field} must include a UTC offset or timezone."
            )
        return parsed
