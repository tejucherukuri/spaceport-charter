import logging
import time
from datetime import timedelta

from django.db import connection, transaction
from django.db.utils import OperationalError
from django.db.models import F
from django.utils import timezone as django_timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Booking, Ship
from .serializers import (
    BookingCreateSerializer,
    BookingReadSerializer,
    DashboardQuerySerializer,
    DashboardShipSerializer,
    ShipSerializer,
    UnavailabilityQuerySerializer,
)
from .services import (
    CENTRAL,
    BookingConflictError,
    BookingRuleError,
    get_dashboard_ships,
    get_unavailability,
    validate_booking,
)


logger = logging.getLogger(__name__)


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def list_ships(request):
    ships = Ship.objects.all()
    return Response(ShipSerializer(ships, many=True).data)


@api_view(["GET"])
def ship_unavailability(request, ship_id):
    query = UnavailabilityQuerySerializer(data=request.query_params)
    query.is_valid(raise_exception=True)
    ship = Ship.objects.filter(pk=ship_id).only("id").first()
    if ship is None:
        return Response(
            {"detail": "Ship not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    availability = get_unavailability(ship.id, query.validated_data["date"])
    return Response({"shipId": ship.id, **availability})


@api_view(["GET"])
def fleet_dashboard(request):
    query_data = {}
    if "from" in request.query_params:
        query_data["from_date"] = request.query_params["from"]
    if "to" in request.query_params:
        query_data["to"] = request.query_params["to"]

    query = DashboardQuerySerializer(data=query_data)
    query.is_valid(raise_exception=True)
    today = django_timezone_now_central_date()
    from_date = query.validated_data.get("from_date", today)
    to_date = query.validated_data.get("to", from_date + timedelta(days=14))

    if to_date < from_date:
        return Response(
            {"detail": "`to` must not be before `from`."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    if (to_date - from_date).days > 366:
        return Response(
            {"detail": "Date range may not exceed 366 days."},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    ships = get_dashboard_ships(from_date, to_date)
    return Response(
        {
            "from": from_date.isoformat(),
            "to": to_date.isoformat(),
            "ships": DashboardShipSerializer(ships, many=True).data,
        }
    )


def django_timezone_now_central_date():
    return django_timezone.now().astimezone(CENTRAL).date()


@api_view(["POST"])
def create_booking(request):
    serializer = BookingCreateSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    ship_id = data["ship_id"]

    try:
        for attempt in range(6):
            try:
                with transaction.atomic():
                    if connection.vendor == "sqlite":
                        # SQLite has no row locks. Begin this transaction with a
                        # write so checks for this ship serialize before reading.
                        locked = Ship.objects.filter(pk=ship_id).update(name=F("name"))
                        if not locked:
                            raise Ship.DoesNotExist
                        ship = Ship.objects.get(pk=ship_id)
                    else:
                        ship = Ship.objects.select_for_update().get(pk=ship_id)

                    start_time, end_time = validate_booking(
                        ship.id,
                        data["start_time"],
                        data["end_time"],
                    )
                    booking = Booking.objects.create(
                        ship=ship,
                        pilot_name=data["pilot_name"],
                        start_time=start_time,
                        end_time=end_time,
                    )
                break
            except OperationalError as exc:
                is_sqlite_lock = (
                    connection.vendor == "sqlite" and "locked" in str(exc).lower()
                )
                if not is_sqlite_lock or attempt == 5:
                    raise
                # Shared-cache SQLite can report SQLITE_LOCKED without honoring
                # busy_timeout. Retry the whole rolled-back transaction briefly.
                logger.warning(
                    "SQLite booking lock encountered for ship %s; retrying attempt %s.",
                    ship_id,
                    attempt + 1,
                )
                time.sleep(0.01 * (2**attempt))
    except Ship.DoesNotExist:
        return Response(
            {"detail": "Ship not found."},
            status=status.HTTP_404_NOT_FOUND,
        )
    except BookingConflictError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_409_CONFLICT,
        )
    except BookingRuleError as exc:
        return Response(
            {"detail": str(exc)},
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    return Response(
        BookingReadSerializer(booking).data,
        status=status.HTTP_201_CREATED,
    )
