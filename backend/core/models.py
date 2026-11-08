from django.db import models
from django.db.models import F, Q


class Ship(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class Booking(models.Model):
    ship = models.ForeignKey(
        Ship,
        on_delete=models.PROTECT,
        related_name="bookings",
    )
    pilot_name = models.CharField(max_length=100)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    class Meta:
        ordering = ["start_time", "id"]
        indexes = [
            models.Index(fields=["ship", "start_time"], name="booking_ship_start_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="booking_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.ship}: {self.pilot_name} ({self.start_time}–{self.end_time})"
