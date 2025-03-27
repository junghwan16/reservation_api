from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers

from slots.models import Slot
from slots.serializers import SlotSerializer

from .models import Reservation, ReservationSlot

User = get_user_model()


class ReservationSerializer(serializers.ModelSerializer):
    slot_ids = serializers.PrimaryKeyRelatedField(
        queryset=Slot.objects.all(),
        many=True,
        write_only=True,
        source='slots',
        help_text="예약할 슬롯 ID 목록"
    )
    slots = SlotSerializer(many=True, read_only=True)
    user = serializers.PrimaryKeyRelatedField(read_only=True)  # 읽기 전용으로 변경
    username = serializers.CharField(source='user.username', read_only=True)

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
        read_only_fields = ["status", "created_at", "updated_at", "user"]  # user를 read_only_fields에 추가

    def validate(self, data):
        # 총 참석자 수 검증 - 최대 수용 인원을 초과할 수 없음
        if "total_attendees" in data and data["total_attendees"] > Slot.MAX_CAPACITY:
            raise serializers.ValidationError(
                f"총 참석자 수는 최대 수용 인원({Slot.MAX_CAPACITY}명)을 초과할 수 없습니다."
            )
            
        # 슬롯 시간 제한 검증
        slots = data.get('slots', [])
        
        if slots:
            # 3일 전 제한 검증
            now = timezone.now()
            three_days_later = now + timezone.timedelta(hours=72)

            for slot in slots:
                if slot.slot_start_time < three_days_later:
                    raise serializers.ValidationError(
                        f"슬롯 {slot.id}는 시작 시간이 3일 이내입니다. "
                        "예약은 슬롯 시작 시간으로부터 최소 72시간 전에 이루어져야 합니다."
                    )

        return data

    def create(self, validated_data):
        # 슬롯 데이터 추출
        slots = validated_data.pop('slots', [])
        
        # 예약 생성
        reservation = Reservation.objects.create(**validated_data)
        
        # 슬롯 연결
        for slot in slots:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)
            
        return reservation

    def update(self, instance, validated_data):
        # 확정된 예약은 수정 불가
        if instance.status == Reservation.STATUS_CONFIRMED:
            raise serializers.ValidationError("확정된 예약은 수정할 수 없습니다.")
            
        # 슬롯 데이터 추출
        slots = validated_data.pop('slots', None)
        
        # 기본 필드 업데이트
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # 슬롯 업데이트
        if slots is not None:
            # 기존 슬롯 연결 삭제
            instance.reservation_slots.all().delete()
            
            # 새 슬롯 연결
            for slot in slots:
                ReservationSlot.objects.create(reservation=instance, slot=slot)
                
        return instance
