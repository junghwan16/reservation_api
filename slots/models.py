from django.db import models


class Slot(models.Model):
    MAX_CAPACITY = 50000  # 최대 수용 인원 상수화

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
        """슬롯의 남은 수용 인원을 계산합니다."""
        return self.MAX_CAPACITY - self.capacity_used

    def __str__(self) -> str:
        return f"{self.slot_start_time.strftime('%Y-%m-%d %H:%M')} ~ {self.slot_end_time.strftime('%H:%M')}"
