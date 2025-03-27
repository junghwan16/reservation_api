from django.db import models
from django.utils import timezone


class Slot(models.Model):
    MAX_CAPACITY = 50000  # 최대 수용 인원

    slot_start_time = models.DateTimeField(db_index=True)
    slot_end_time = models.DateTimeField()
    capacity_used = models.BigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["slot_start_time"]),
        ]
        ordering = ["slot_start_time"]

    def remaining_capacity(self) -> int:
        """남은 수용 인원을 계산합니다."""
        return self.MAX_CAPACITY - self.capacity_used

    def is_available(self) -> bool:
        """슬롯이 예약 가능한지 판단합니다."""
        return self.capacity_used < self.MAX_CAPACITY

    def is_past(self) -> bool:
        """현재 시각 이전인 슬롯인지 확인합니다."""
        return self.slot_end_time < timezone.now()

    def duration_minutes(self) -> int:
        """슬롯의 지속 시간(분)을 계산합니다."""
        delta = self.slot_end_time - self.slot_start_time
        return int(delta.total_seconds() / 60)

    def __str__(self) -> str:
        return f"{self.slot_start_time.strftime('%Y-%m-%d %H:%M')} ~ {self.slot_end_time.strftime('%H:%M')}"
