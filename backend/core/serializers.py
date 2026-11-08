import re

from rest_framework import serializers

from .models import Booking, Ship


class OffsetDateTimeField(serializers.DateTimeField):
    """Accept ISO timestamps only when they identify an unambiguous instant."""

    default_error_messages = {
        "timezone_required": "Timestamp must include a timezone offset, for example -06:00 or Z."
    }

    def to_internal_value(self, value):
        if not isinstance(value, str) or not re.search(
            r"(?:Z|[+-]\d{2}:\d{2})$", value.strip(), re.IGNORECASE
        ):
            self.fail("timezone_required")
        return super().to_internal_value(value)


class ShipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ship
        fields = ["id", "name"]


class UnavailabilityQuerySerializer(serializers.Serializer):
    date = serializers.DateField(input_formats=["%Y-%m-%d"])


class BookingCreateSerializer(serializers.Serializer):
    shipId = serializers.IntegerField(source="ship_id", min_value=1)
    pilotName = serializers.CharField(
        source="pilot_name",
        max_length=100,
        trim_whitespace=True,
        allow_blank=False,
    )
    startTime = OffsetDateTimeField(source="start_time")
    endTime = OffsetDateTimeField(source="end_time")


class BookingReadSerializer(serializers.ModelSerializer):
    shipId = serializers.IntegerField(source="ship_id", read_only=True)
    pilotName = serializers.CharField(source="pilot_name", read_only=True)
    startTime = serializers.DateTimeField(source="start_time", read_only=True)
    endTime = serializers.DateTimeField(source="end_time", read_only=True)

    class Meta:
        model = Booking
        fields = ["id", "shipId", "pilotName", "startTime", "endTime"]
