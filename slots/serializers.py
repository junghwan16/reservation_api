from typing import Dict, Union

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Slot


class SlotSerializer(serializers.ModelSerializer):
    remaining_capacity = serializers.SerializerMethodField()
    max_capacity = serializers.SerializerMethodField()

    class Meta:
        model = Slot
        fields = [
            "id",
            "slot_start_time",
            "slot_end_time",
            "capacity_used",
            "remaining_capacity",
            "max_capacity",
        ]

    @extend_schema_field(serializers.IntegerField)
    def get_remaining_capacity(self, obj: Slot) -> int:
        """슬롯의 남은 수용 인원을 계산합니다."""
        return obj.remaining_capacity()

    @extend_schema_field(serializers.IntegerField)
    def get_max_capacity(self, obj: Slot) -> int:
        """슬롯의 최대 수용 인원을 반환합니다."""
        return Slot.MAX_CAPACITY
