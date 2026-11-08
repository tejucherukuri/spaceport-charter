import logging
import time

from django.db import connection, transaction
from django.db.utils import OperationalError
from django.db.models import F
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Booking, Ship
from .serializers import BookingCreateSerializer, BookingReadSerializer, ShipSerializer
from .services import BookingConflictError, BookingRuleError, validate_booking


logger = logging.getLogger(__name__)


@api_view(["GET"])
def health_check(request):
    return Response({"status": "ok"})


@api_view(["GET"])
def list_ships(request):
    ships = Ship.objects.all()
    return Response(ShipSerializer(ships, many=True).data)


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
