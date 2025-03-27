from rest_framework import serializers

from .models import Slot


class SlotSerializer(serializers.ModelSerializer):
    """
    단일 슬롯의 기본 정보를 직렬화합니다.
    """

    class Meta:
        model = Slot
        fields = ["id", "slot_start_time", "slot_end_time", "capacity_used"]


class AvailableDateSerializer(serializers.Serializer):
    """
    날짜별로 'available_slots_count' 집계 결과를 직렬화합니다.
    예: {"date": "2025-04-15", "available_slots_count": 48}
    """

    date = serializers.DateField()
    available_slots_count = serializers.IntegerField()
