from typing import List

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from slots.models import Slot

User = get_user_model()


class Reservation(models.Model):
    # 상태 상수 정의
    STATUS_PENDING = "PENDING"
    STATUS_CONFIRMED = "CONFIRMED"

    STATUS_CHOICES = (
        (STATUS_PENDING, _("Pending")),
        (STATUS_CONFIRMED, _("Confirmed")),
    )

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="reservations"
    )
    total_attendees = models.BigIntegerField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    slots = models.ManyToManyField(Slot, through="ReservationSlot")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        username = self.user.username if self.user else "Unknown"
        return f"Reservation #{self.id} - User: {username} - Status: {self.status}"

    def get_slot_ids(self) -> List[int]:
        """예약에 포함된 모든 슬롯의 ID 목록을 반환합니다."""
        return list(self.slots.values_list("id", flat=True))


class ReservationSlot(models.Model):
    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name="reservation_slots"
    )
    slot = models.ForeignKey(
        Slot, on_delete=models.CASCADE, related_name="reservation_slots"
    )

    class Meta:
        unique_together = ("reservation", "slot")
        indexes = [
            models.Index(fields=["reservation"]),
            models.Index(fields=["slot"]),
        ]

    def __str__(self) -> str:
        return f"Reservation {self.reservation.id} - Slot {self.slot.id}"
