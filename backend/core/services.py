from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from django.utils import timezone as django_timezone

from .models import Booking


CENTRAL = ZoneInfo("America/Chicago")
OPERATING_OPEN = time(6)
OPERATING_CLOSE = time(22)
REFUEL_BUFFER = timedelta(minutes=30)


class BookingRuleError(ValueError):
    """A booking request violates a fleet booking rule."""


class BookingConflictError(BookingRuleError):
    """A ship is already reserved during the requested time or refuel buffer."""


def validate_booking_times(start_time: datetime, end_time: datetime) -> tuple[datetime, datetime]:
    """Validate a booking window and return both timestamps normalized to UTC."""
    if django_timezone.is_naive(start_time) or django_timezone.is_naive(end_time):
        raise BookingRuleError("Start and end times must include a timezone.")

    start_utc = start_time.astimezone(timezone.utc)
    end_utc = end_time.astimezone(timezone.utc)
    if end_utc <= start_utc:
        raise BookingRuleError("End time must be after start time.")

    start_central = start_utc.astimezone(CENTRAL)
    end_central = end_utc.astimezone(CENTRAL)
    if start_central.date() != end_central.date():
        raise BookingRuleError("A booking must start and end on the same Central Time date.")

    opens_utc = datetime.combine(
        start_central.date(), OPERATING_OPEN, tzinfo=CENTRAL
    ).astimezone(timezone.utc)
    closes_utc = datetime.combine(
        start_central.date(), OPERATING_CLOSE, tzinfo=CENTRAL
    ).astimezone(timezone.utc)
    if start_utc < opens_utc or end_utc > closes_utc:
        raise BookingRuleError(
            "Bookings must fall entirely within 6:00 AM–10:00 PM Central Time."
        )

    return start_utc, end_utc


def validate_booking(
    ship_id: int,
    start_time: datetime,
    end_time: datetime,
    *,
    exclude_booking_id: int | None = None,
) -> tuple[datetime, datetime]:
    """Validate the time window and ensure this ship has the required refuel gap."""
    start_utc, end_utc = validate_booking_times(start_time, end_time)
    conflicts = Booking.objects.filter(
        ship_id=ship_id,
        start_time__lt=end_utc + REFUEL_BUFFER,
        end_time__gt=start_utc - REFUEL_BUFFER,
    )
    if exclude_booking_id is not None:
        conflicts = conflicts.exclude(pk=exclude_booking_id)

    if conflicts.exists():
        raise BookingConflictError(
            "Ship is unavailable: the requested time overlaps another booking "
            "or its 30-minute refueling buffer."
        )

    return start_utc, end_utc
