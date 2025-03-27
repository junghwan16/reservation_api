from django.db import transaction
from django.db.models import F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied

from slots.models import Slot

from .models import Reservation, ReservationSlot
from .serializers import ReservationSerializer


class IsAdminOrOwnReservation(permissions.BasePermission):
    """관리자 또는 예약의 소유자만 접근할 수 있도록 하는 권한"""

    def has_permission(self, request, view):
        # 관리자는 항상 접근 가능
        if request.user.is_staff:
            return True

        # 인증된 사용자인지 확인
        if not request.user.is_authenticated:
            return False

        # 예약 목록 조회 및 생성은 인증된 사용자 모두 가능
        if view.action in ['list', 'create']:
            return True

        return True  # 다른 액션은 has_object_permission에서 확인

    def has_object_permission(self, request, view, obj):
        # 관리자는 항상 접근 가능
        if request.user.is_staff:
            return True

        # 예약 확정(confirm)은 관리자만 가능
        if view.action == 'confirm':
            return False
            
        # 소유자 확인
        return obj.user and obj.user == request.user


class ReservationViewSet(viewsets.ModelViewSet):
    """
    예약 관리를 위한 API 뷰셋입니다.
    
    예약 시스템은 다음과 같은 규칙을 따릅니다:
    1. 예약은 슬롯 시작 시간으로부터 최소 72시간 전에 이루어져야 합니다.
    2. 예약은 처음에 PENDING 상태로 생성되고, 관리자가 확인 후 CONFIRMED 상태로 변경됩니다.
    3. CONFIRMED 상태의 예약은 수정할 수 없습니다.
    4. 최대 수용 인원(Slot.MAX_CAPACITY)을 초과하는 예약은 확정할 수 없습니다.
    
    사용 가능한 엔드포인트:
    - GET /api/reservations/ - 예약 목록 조회 (관리자: 모든 예약, 일반 사용자: 자신의 예약)
    - POST /api/reservations/ - 새 예약 생성
    - GET /api/reservations/{id}/ - 특정 예약 상세 조회
    - PUT/PATCH /api/reservations/{id}/ - 예약 수정 (PENDING 상태만)
    - DELETE /api/reservations/{id}/ - 예약 삭제
    - POST /api/reservations/{id}/confirm/ - 예약 확정 (관리자 전용)
    """

    # 상수 정의
    RESERVATION_MIN_HOURS = 72  # 예약 가능한 최소 시간 (3일)

    queryset = Reservation.objects.all().order_by("-created_at")
    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnReservation]

    def get_queryset(self):
        """사용자별 예약 필터링"""
        queryset = super().get_queryset()
        
        # 관리자가 아닌 경우 자신의 예약만 볼 수 있음
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)
            
        return queryset

    def perform_create(self, serializer):
        """현재 사용자를 예약 소유자로 설정"""
        serializer.save(user=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        새 예약을 생성합니다.
        
        트랜잭션을 사용하여 일관성을 보장하고, 시리얼라이저를 통해 유효성을 검증합니다.
        현재 인증된 사용자가 자동으로 예약의 소유자로 설정됩니다.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # perform_create에서 현재 사용자를 예약 소유자로 설정
        self.perform_create(serializer)
        
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, 
            status=status.HTTP_201_CREATED, 
            headers=headers
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        예약을 수정합니다.
        
        트랜잭션을 사용하여 일관성을 보장하고, PENDING 상태가 아닌 예약은 수정할 수 없습니다.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # 시리얼라이저에서 상태 검증을 수행
        serializer = self.get_serializer(
            instance, 
            data=request.data, 
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        
        self.perform_update(serializer)

        return Response(
            {"message": "예약이 성공적으로 수정되었습니다", "data": serializer.data},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"])
    @extend_schema(
        summary="예약 확정",
        description="예약을 확정합니다. 관리자만 이 작업을 수행할 수 있습니다. 슬롯의 용량을 확인하고 예약을 확정합니다.",
        tags=["예약"],
        request=None,
    )
    @transaction.atomic
    def confirm(self, request, pk=None):
        """
        예약을 확정합니다.
        
        이 작업은 관리자만 수행할 수 있으며, 슬롯의 용량을 확인한 후 예약을 확정합니다.
        트랜잭션과 비관적 락(SELECT FOR UPDATE)을 사용하여 동시성 문제를 방지합니다.
        """
        # 권한 검사는 permission_classes로 처리됨
        reservation = self.get_object()

        # 이미 확정된 예약인지 확인
        if reservation.status == Reservation.STATUS_CONFIRMED:
            raise ValidationError({"error": "이미 확정된 예약입니다."})

        # 수용 인원 초과 여부 확인 및 슬롯 업데이트
        slot_ids = reservation.get_slot_ids()
        
        # 비관적 락으로 슬롯 조회
        slots = Slot.objects.filter(id__in=slot_ids).select_for_update()

        # 모든 슬롯에서 수용 인원 초과 여부 확인
        for slot in slots:
            if slot.capacity_used + reservation.total_attendees > Slot.MAX_CAPACITY:
                error_message = (
                    f"슬롯 {slot.id}의 수용 인원을 초과했습니다. "
                    f"현재 사용: {slot.capacity_used}, 요청: {reservation.total_attendees}, "
                    f"최대: {Slot.MAX_CAPACITY}"
                )
                raise ValidationError({"error": error_message})

        try:
            # 모든 슬롯에 예약 인원 추가
            for slot in slots:
                # F 표현식을 사용하여 race condition 방지
                slot.capacity_used = F("capacity_used") + reservation.total_attendees
                slot.save()

            # 예약 상태 업데이트
            reservation.status = Reservation.STATUS_CONFIRMED
            reservation.save()
        except Exception as e:
            # 롤백은 트랜잭션 데코레이터에 의해 자동으로 처리됨
            raise ValidationError({"error": f"예약 확정 중 오류가 발생했습니다: {str(e)}"})

        return Response(
            {
                "message": "예약이 성공적으로 확정되었습니다",
                "data": ReservationSerializer(reservation).data,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        """
        예약을 삭제합니다.
        
        CONFIRMED 상태인 경우 슬롯의 capacity_used를 감소시킵니다.
        트랜잭션과 비관적 락을 사용하여 일관성을 유지합니다.
        """
        reservation = self.get_object()

        # CONFIRMED 상태인 경우, 슬롯 capacity_used 감소
        if reservation.status == Reservation.STATUS_CONFIRMED:
            slot_ids = reservation.get_slot_ids()
            
            # 비관적 락으로 슬롯 조회
            slots = Slot.objects.filter(id__in=slot_ids).select_for_update()

            # 모든 슬롯에서 예약 인원 제거
            for slot in slots:
                # 음수가 되지 않도록 방지
                new_capacity = max(0, slot.capacity_used - reservation.total_attendees)
                slot.capacity_used = new_capacity
                slot.save()

        # 예약 삭제
        self.perform_destroy(reservation)
        return Response(status=status.HTTP_204_NO_CONTENT)
