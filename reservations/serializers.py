from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from slots.models import Slot
from slots.serializers import SlotSerializer

from .models import Reservation, ReservationSlot

User = get_user_model()


class ReservationSerializer(serializers.ModelSerializer):
    slot_ids = serializers.ListField(
        child=serializers.IntegerField(), write_only=True, required=False
    )
    slots = SlotSerializer(many=True, read_only=True)
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    username = serializers.SerializerMethodField(read_only=True)

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
        read_only_fields = ["status", "created_at", "updated_at", "username"]

    def get_username(self, obj):
        """사용자 이름을 반환합니다."""
        return obj.user.username if obj.user else None

    def validate(self, data):
        # 총 참석자 수 검증 - 최대 수용 인원(50,000명)을 초과할 수 없음
        if "total_attendees" in data and data["total_attendees"] > Slot.MAX_CAPACITY:
            raise serializers.ValidationError(
                f"총 참석자 수는 최대 수용 인원({Slot.MAX_CAPACITY}명)을 초과할 수 없습니다."
            )
            
        # 슬롯 ID가 제공된 경우 검증
        if "slot_ids" in data:
            slot_ids = data["slot_ids"]

            # 슬롯이 존재하는지 확인
            slots = Slot.objects.filter(id__in=slot_ids)
            if len(slots) != len(slot_ids):
                raise serializers.ValidationError("일부 슬롯이 존재하지 않습니다.")

            # 3일 전 제한 검증
            now = timezone.now()
            three_days_later = now + timezone.timedelta(hours=72)

            for slot in slots:
                if slot.slot_start_time < three_days_later:
                    raise serializers.ValidationError(
                        f"슬롯 {slot.id}는 시작 시간이 3일 이내입니다. 예약은 슬롯 시작 시간으로부터 최소 72시간 전에 이루어져야 합니다."
                    )

        return data

    def create(self, validated_data):
        slot_ids = validated_data.pop("slot_ids", [])
        reservation = Reservation.objects.create(**validated_data)

        # 슬롯 연결
        for slot_id in slot_ids:
            ReservationSlot.objects.create(reservation=reservation, slot_id=slot_id)

        return reservation

    def update(self, instance, validated_data):
        if instance.status == "CONFIRMED":
            raise serializers.ValidationError("확정된 예약은 수정할 수 없습니다.")

        slot_ids = validated_data.pop("slot_ids", None)

        # 기본 필드 업데이트
        instance.total_attendees = validated_data.get(
            "total_attendees", instance.total_attendees
        )

        # user 필드 업데이트
        instance.user = validated_data.get("user", instance.user)

        instance.save()

        # 슬롯 업데이트
        if slot_ids is not None:
            # 기존 슬롯 연결 삭제
            instance.reservation_slots.all().delete()

            # 새 슬롯 연결
            for slot_id in slot_ids:
                ReservationSlot.objects.create(reservation=instance, slot_id=slot_id)

        return instance
