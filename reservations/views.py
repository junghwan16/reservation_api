from django.db import transaction
from django.db.models import F
from django.shortcuts import render
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from slots.models import Slot

from .models import Reservation, ReservationSlot
from .serializers import ReservationSerializer


class IsAdminOrOwnReservation(permissions.BasePermission):
    """
    관리자 또는 예약의 소유자만 접근할 수 있도록 하는 권한
    """

    def has_permission(self, request, view):
        # 관리자는 항상 접근 가능
        if request.user.is_staff:
            return True

        # 인증된 사용자인지 확인
        if not request.user.is_authenticated:
            return False

        # 예약 목록 조회는 인증된 사용자 모두 가능
        if view.action == "list":
            return True

        # 인증된 사용자만 예약 생성 가능
        if view.action == "create":
            return request.user.is_authenticated

        return True  # 다른 액션은 has_object_permission에서 확인

    def has_object_permission(self, request, view, obj):
        # 관리자는 항상 접근 가능
        if request.user.is_staff:
            return True

        # 소유자 확인 (user 필드가 요청 사용자와 일치하는지)
        if obj.user and obj.user == request.user:
            return True

        # 예약 확정은 관리자만 가능
        if view.action == "confirm" and not request.user.is_staff:
            return False

        return False


@extend_schema_view(
    create=extend_schema(
        summary="새 예약 생성",
        description="새로운 예약을 생성합니다. 현재 로그인한 사용자가 자동으로 예약의 소유자가 됩니다.",
        tags=["예약"],
        examples=[
            OpenApiExample(
                "예약 생성 예제",
                value={
                    "total_attendees": 10, 
                    "slot_ids": [1, 2, 3]
                },
                request_only=True,
            )
        ]
    ),
    list=extend_schema(
        summary="예약 목록 조회", 
        description="관리자는 모든 예약을, 일반 사용자는 자신의 예약만 조회할 수 있습니다.", 
        tags=["예약"]
    ),
    retrieve=extend_schema(
        summary="예약 상세 조회", 
        description="특정 예약의 상세 정보를 조회합니다.", 
        tags=["예약"]
    ),
    update=extend_schema(
        summary="예약 전체 수정", 
        description="예약 정보를 전체 수정합니다. PENDING 상태의 예약만 수정 가능합니다.", 
        tags=["예약"],
        examples=[
            OpenApiExample(
                "예약 수정 예제",
                value={
                    "total_attendees": 20, 
                    "slot_ids": [1, 2]
                },
                request_only=True,
            )
        ]
    ),
    partial_update=extend_schema(
        summary="예약 부분 수정", 
        description="예약 정보를 부분 수정합니다. PENDING 상태의 예약만 수정 가능합니다.", 
        tags=["예약"],
        examples=[
            OpenApiExample(
                "예약 부분 수정 예제",
                value={
                    "total_attendees": 30
                },
                request_only=True,
            )
        ]
    ),
    destroy=extend_schema(
        summary="예약 삭제", 
        description="예약을 삭제합니다. CONFIRMED 상태인 경우 슬롯의 사용 인원을 감소시킵니다.", 
        tags=["예약"]
    ),
)
class ReservationViewSet(viewsets.ModelViewSet):
    """
    예약 관리를 위한 API 뷰셋입니다.
    GET /api/reservations/ - 모든 예약을 반환합니다. (관리자만 접근 가능)
    GET /api/reservations/ - 인증된 사용자의 예약을 반환합니다.
    POST /api/reservations/ - 새 예약을 생성합니다.
    PATCH /api/reservations/:id/ - 예약을 수정합니다. (PENDING 상태의 예약만 가능)
    DELETE /api/reservations/:id/ - 예약을 삭제합니다.
    POST /api/reservations/:id/confirm/ - 예약을 확정합니다. (관리자만 접근 가능)
    """

    # 상수 정의
    RESERVATION_MIN_HOURS = 72  # 예약 가능한 최소 시간 (3일)

    queryset = Reservation.objects.all().order_by("-created_at")
    serializer_class = ReservationSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsAdminOrOwnReservation,
    ]  # 권한 클래스 활성화

    def get_queryset(self):
        queryset = super().get_queryset()

        # 관리자가 아닌 경우 자신의 예약만 볼 수 있음
        if not self.request.user.is_staff:
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def _validate_slot_time_restriction(self, slot_ids):
        """슬롯 시간 제한 검증 - 시험 시작 3일 전부터는 예약 불가"""
        if not slot_ids:
            return None, None

        # 비관적 락으로 슬롯 조회
        slots = Slot.objects.filter(id__in=slot_ids).select_for_update()

        # 시간 제한 확인
        min_start_time = timezone.now() + timezone.timedelta(
            hours=self.RESERVATION_MIN_HOURS
        )
        for slot in slots:
            if slot.slot_start_time < min_start_time:
                return Response(
                    {
                        "error": f"슬롯 {slot.id}는 시험 시작 3일 전이므로 예약할 수 없습니다."
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                ), None

        return None, slots

    def create(self, request, *args, **kwargs):
        """
        새 예약을 생성합니다. 시험 시작 3일 전까지만 예약 가능합니다.
        """
        # 현재 로그인한 사용자 정보를 요청 데이터에 추가
        data = request.data.copy()
        data["user"] = request.user.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

        # 트랜잭션과 비관적 락 적용
        with transaction.atomic():
            slot_ids = serializer.validated_data.get("slot_ids", [])

            # 시간 제한 검증
            error_response, _ = self._validate_slot_time_restriction(slot_ids)
            if error_response:
                return error_response

            self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def update(self, request, *args, **kwargs):
        """
        예약을 수정합니다. PENDING 상태의 예약만 수정 가능합니다.
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        # PENDING 상태 확인
        if instance.status != Reservation.STATUS_PENDING:
            return Response(
                {"error": "확정된 예약은 수정할 수 없습니다."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 현재 사용자 ID를 요청 데이터에 추가
        if instance.user is None and request.user.is_authenticated:
            data = request.data.copy()
            data["user"] = request.user.id
            serializer = self.get_serializer(instance, data=data, partial=partial)
        else:
            serializer = self.get_serializer(
                instance, data=request.data, partial=partial
            )

        serializer.is_valid(raise_exception=True)

        # 트랜잭션과 비관적 락 적용
        with transaction.atomic():
            # 슬롯이 변경되었다면 시간 제한 재확인
            if "slot_ids" in serializer.validated_data:
                slot_ids = serializer.validated_data.get("slot_ids", [])

                # 시간 제한 검증
                error_response, _ = self._validate_slot_time_restriction(slot_ids)
                if error_response:
                    return error_response

            self.perform_update(serializer)

        return Response(
            {"message": "예약이 성공적으로 수정되었습니다", "data": serializer.data},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    @transaction.atomic
    @extend_schema(
        summary="예약 확정",
        description="예약을 확정합니다. 관리자만 이 작업을 수행할 수 있습니다. 슬롯의 용량을 확인하고 예약을 확정합니다.",
        tags=["예약"],
        request=None,
    )
    def confirm(self, request, pk=None):
        """
        예약을 확정합니다. 이 작업은 관리자만 수행할 수 있습니다.
        """
        # 관리자 권한 확인
        if not request.user.is_staff:
            return Response(
                {"error": "이 작업을 수행할 권한이 없습니다."},
                status=status.HTTP_403_FORBIDDEN,
            )

        reservation = self.get_object()

        # 이미 확정된 예약인지 확인
        if reservation.status == Reservation.STATUS_CONFIRMED:
            return Response(
                {"error": "이미 확정된 예약입니다."}, status=status.HTTP_400_BAD_REQUEST
            )

        # 수용 인원 초과 여부 확인
        slot_ids = reservation.get_slot_ids()
        slots = Slot.objects.filter(id__in=slot_ids).select_for_update()

        # 모든 슬롯에서 수용 인원 초과 여부 확인
        for slot in slots:
            if slot.capacity_used + reservation.total_attendees > Slot.MAX_CAPACITY:
                error_message = (
                    f"슬롯 {slot.id}의 수용 인원을 초과했습니다. "
                    f"현재 사용: {slot.capacity_used}, 요청: {reservation.total_attendees}, "
                    f"최대: {Slot.MAX_CAPACITY}"
                )
                return Response(
                    {"error": error_message}, status=status.HTTP_400_BAD_REQUEST
                )

        # 모든 슬롯에 예약 인원 추가
        for slot in slots:
            slot.capacity_used = F("capacity_used") + reservation.total_attendees
            slot.save()

        # 예약 상태 업데이트
        reservation.status = Reservation.STATUS_CONFIRMED
        reservation.save()

        return Response(
            {
                "message": "예약이 성공적으로 확정되었습니다",
                "data": ReservationSerializer(reservation).data,
            },
            status=status.HTTP_200_OK,
        )

    def destroy(self, request, *args, **kwargs):
        """
        예약을 삭제합니다. CONFIRMED 상태인 경우, 슬롯의 capacity_used를 감소시킵니다.
        """
        reservation = self.get_object()

        # CONFIRMED 상태인 경우, 슬롯 capacity_used 감소
        if reservation.status == Reservation.STATUS_CONFIRMED:
            with transaction.atomic():
                slot_ids = reservation.get_slot_ids()
                slots = Slot.objects.filter(id__in=slot_ids).select_for_update()

                # 모든 슬롯에서 예약 인원 제거
                for slot in slots:
                    slot.capacity_used = (
                        F("capacity_used") - reservation.total_attendees
                    )
                    slot.save()

        # 예약 삭제
        self.perform_destroy(reservation)
        return Response(status=status.HTTP_204_NO_CONTENT)
