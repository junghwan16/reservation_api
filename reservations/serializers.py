from django.utils import timezone
from rest_framework import serializers

from slots.models import Slot
from slots.serializers import SlotSerializer

from .models import Reservation, ReservationSlot


class ReservationSerializer(serializers.ModelSerializer):
    """
    예약 데이터 직렬화/역직렬화 및 검증
    """

    slot_ids = serializers.PrimaryKeyRelatedField(
        queryset=Slot.objects.all(),
        many=True,
        write_only=True,
        source="slots",
        help_text="예약할 슬롯 ID 목록입니다. 시작 시간이 72시간 이내인 슬롯은 예약할 수 없습니다.",
    )
    slots = SlotSerializer(
        many=True,
        read_only=True,
        help_text="예약된 슬롯의 상세 정보 목록입니다.",
    )
    username = serializers.CharField(
        source="user.username",
        read_only=True,
        help_text="예약한 사용자의 username입니다.",
    )

    class Meta:
        model = Reservation
        fields = [
            "id",
            "user",
            "username",
            "total_attendees",
            "status",
            "slot_ids",
            "slots",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["status", "created_at", "updated_at", "user"]

    def validate_total_attendees(self, value):
        """
        총 참석자 수가 슬롯 최대 수용 인원 초과 시 검증 오류 발생
        """
        if value > Slot.MAX_CAPACITY:
            raise serializers.ValidationError(
                f"총 참석자 수는 최대 수용 인원({Slot.MAX_CAPACITY}명)을 초과할 수 없습니다."
            )
        return value

    def validate_slot_ids(self, slots):
        """
        슬롯 시작 시간이 현재 시각으로부터 72시간 미만이면 예약할 수 없음
        """
        if not slots:
            return slots

        now = timezone.now()
        min_start_time = now + timezone.timedelta(hours=72)
        invalid_slots = [
            slot for slot in slots if slot.slot_start_time < min_start_time
        ]

        if invalid_slots:
            slot_ids = ", ".join(str(slot.id) for slot in invalid_slots)
            raise serializers.ValidationError(
                f"슬롯 {slot_ids}는 시작 시간이 72시간 이내여서 예약할 수 없습니다."
            )
        return slots

    def _assign_slots(self, reservation: Reservation, slots: list[Slot]):
        if slots is None:
            return
        reservation.reservation_slots.all().delete()
        ReservationSlot.objects.bulk_create(
            [ReservationSlot(reservation=reservation, slot=slot) for slot in slots]
        )

    def create(self, validated_data):
        slots = validated_data.pop("slots", [])
        reservation = Reservation.objects.create(**validated_data)
        self._assign_slots(reservation, slots)
        return reservation

    def update(self, instance, validated_data):
        slots = validated_data.pop("slots", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        self._assign_slots(instance, slots)
        return instance
