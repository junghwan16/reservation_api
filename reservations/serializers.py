from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied

from slots.models import Slot
from slots.serializers import SlotSerializer

from .models import Reservation, ReservationSlot

User = get_user_model()


class ReservationSerializer(serializers.ModelSerializer):
    slot_ids = serializers.PrimaryKeyRelatedField(
        queryset=Slot.objects.all(),
        many=True,
        write_only=True,
        source="slots",
        help_text="예약할 슬롯 ID 목록",
    )
    slots = SlotSerializer(many=True, read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)

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
        read_only_fields = [
            "status",
            "created_at",
            "updated_at",
            "user",
        ]

    def validate_total_attendees(self, value):
        """총 참석자 수가 최대 수용 인원을 초과하지 않는지 검증"""
        if value > Slot.MAX_CAPACITY:
            raise serializers.ValidationError(
                f"총 참석자 수는 최대 수용 인원({Slot.MAX_CAPACITY}명)을 초과할 수 없습니다."
            )
        return value

    def validate_slots(self, slots):
        """슬롯들이 예약 가능한 시간대인지 검증"""
        if not slots:
            return slots

        now = timezone.now()
        three_days_later = now + timezone.timedelta(hours=72)

        invalid_slots = [
            slot for slot in slots 
            if slot.slot_start_time < three_days_later
        ]

        if invalid_slots:
            slot_ids = ", ".join(str(slot.id) for slot in invalid_slots)
            raise serializers.ValidationError(
                f"슬롯 {slot_ids}는 시작 시간이 3일 이내입니다. "
                "예약은 슬롯 시작 시간으로부터 최소 72시간 전에 이루어져야 합니다."
            )

        return slots

    def validate(self, data):
        """데이터 유효성 검증"""
        if "total_attendees" in data:
            self.validate_total_attendees(data["total_attendees"])
        
        if "slots" in data:
            self.validate_slots(data["slots"])

        return data

    def _handle_slots(self, reservation, slots):
        """예약에 슬롯을 연결하는 내부 메서드"""
        if slots is None:
            return

        # 기존 슬롯 연결 삭제
        reservation.reservation_slots.all().delete()

        # 새 슬롯 연결
        ReservationSlot.objects.bulk_create([
            ReservationSlot(reservation=reservation, slot=slot)
            for slot in slots
        ])

    def create(self, validated_data):
        """새로운 예약 생성"""
        # 슬롯 데이터 분리
        slots = validated_data.pop("slots", [])

        # 예약 생성
        reservation = Reservation.objects.create(**validated_data)

        # 슬롯 연결
        self._handle_slots(reservation, slots)

        return reservation

    def _can_update_confirmed_reservation(self):
        """CONFIRMED 상태의 예약을 수정할 수 있는지 확인"""
        return self.context['request'].user.is_staff

    def update(self, instance, validated_data):
        """예약 정보 수정"""
        # CONFIRMED 상태 검증
        if not self._can_update_confirmed_reservation() and instance.status == Reservation.STATUS_CONFIRMED:
            raise serializers.ValidationError("확정된 예약은 수정할 수 없습니다.")

        # 슬롯 데이터 분리
        slots = validated_data.pop("slots", None)

        # 기본 필드 업데이트
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # 슬롯 업데이트
        self._handle_slots(instance, slots)

        return instance
