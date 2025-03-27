from django.db import transaction
from django.db.models import F
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from slots.models import Slot

from .models import Reservation
from .permissions import IsAdminOrOwnReservation
from .serializers import ReservationSerializer


@extend_schema_view(
    list=extend_schema(
        summary="예약 목록 조회",
        description="현재 사용자의 예약 목록을 페이지네이션된 형태로 반환합니다. 관리자는 모든 예약을 조회할 수 있습니다.",
    ),
    retrieve=extend_schema(
        summary="예약 상세 조회", description="예약 ID에 따른 상세 정보를 반환합니다."
    ),
    create=extend_schema(
        summary="예약 생성",
        description="새로운 예약을 생성합니다. 요청 본문에는 total_attendees와 slot_ids가 필요하며, 현재 로그인한 사용자가 자동으로 예약 소유자로 설정됩니다.",
    ),
    update=extend_schema(
        summary="예약 수정",
        description="예약 정보를 수정합니다. 일반 사용자는 PENDING 상태의 예약만 수정할 수 있습니다.",
    ),
    partial_update=extend_schema(
        summary="예약 부분 수정", description="예약 정보를 일부 수정합니다."
    ),
    destroy=extend_schema(
        summary="예약 삭제",
        description="예약을 삭제합니다. CONFIRMED 상태의 예약 삭제 시 슬롯 capacity_used가 복구됩니다.",
    ),
    confirm=extend_schema(
        summary="예약 확정",
        description="관리자 전용 예약 확정 액션입니다. (요청 본문 없음)",
        request=None,  # confirm 액션은 body가 필요 없음
        responses={200: ReservationSerializer},
    ),
)
class ReservationViewSet(viewsets.ModelViewSet):
    """
    예약 관리를 위한 API 뷰셋.

    전역 PageNumberPagination 설정에 따라 목록 조회 시
    {"count": ..., "results": [...]} 형태로 반환됩니다.
    """

    queryset = Reservation.objects.all().order_by("-created_at")
    serializer_class = ReservationSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwnReservation]

    def get_queryset(self):
        if self.request.user.is_staff:
            return super().get_queryset()
        return super().get_queryset().filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        old_status = instance.status
        old_slot_ids = instance.get_slot_ids()

        if old_status == Reservation.STATUS_CONFIRMED:
            old_slots = Slot.objects.filter(id__in=old_slot_ids).select_for_update()
            for slot in old_slots:
                slot.capacity_used = F("capacity_used") - instance.total_attendees
                slot.save()

        response = super().update(request, partial=partial, *args, **kwargs)
        updated_instance = self.get_object()
        if updated_instance.status == Reservation.STATUS_CONFIRMED:
            new_slot_ids = updated_instance.get_slot_ids()
            new_slots = Slot.objects.filter(id__in=new_slot_ids).select_for_update()
            for slot in new_slots:
                if (
                    slot.capacity_used + updated_instance.total_attendees
                    > Slot.MAX_CAPACITY
                ):
                    raise ValidationError(
                        f"슬롯 {slot.id}의 수용 인원을 초과했습니다. (현재 {slot.capacity_used}, 요청 {updated_instance.total_attendees}, 최대 {Slot.MAX_CAPACITY})"
                    )
                slot.capacity_used = (
                    F("capacity_used") + updated_instance.total_attendees
                )
                slot.save()
        return response

    @action(detail=True, methods=["post"])
    @transaction.atomic
    @extend_schema(
        request=None,  # confirm 액션은 본문이 필요 없음
        responses={200: ReservationSerializer},
        summary="예약 확정",
        description="관리자 전용 예약 확정 액션. 슬롯 capacity를 검증 및 업데이트한 후, 예약 상태를 CONFIRMED로 변경합니다.",
    )
    def confirm(self, request, pk=None):
        reservation = self.get_object()
        if reservation.status == Reservation.STATUS_CONFIRMED:
            raise ValidationError("이미 확정된 예약입니다.")

        slot_ids = reservation.get_slot_ids()
        slots = Slot.objects.filter(id__in=slot_ids).select_for_update()
        for slot in slots:
            if slot.capacity_used + reservation.total_attendees > Slot.MAX_CAPACITY:
                raise ValidationError(
                    f"슬롯 {slot.id}의 수용 인원을 초과했습니다. (현재 {slot.capacity_used}, 요청 {reservation.total_attendees}, 최대 {Slot.MAX_CAPACITY})"
                )

        for slot in slots:
            slot.capacity_used = F("capacity_used") + reservation.total_attendees
            slot.save()

        reservation.status = Reservation.STATUS_CONFIRMED
        reservation.save()

        return Response(
            {
                "message": "예약이 성공적으로 확정되었습니다.",
                "data": self.get_serializer(reservation).data,
            },
            status=status.HTTP_200_OK,
        )

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        reservation = self.get_object()
        if reservation.status == Reservation.STATUS_CONFIRMED:
            slot_ids = reservation.get_slot_ids()
            slots = Slot.objects.filter(id__in=slot_ids).select_for_update()
            for slot in slots:
                slot.capacity_used = max(
                    0, slot.capacity_used - reservation.total_attendees
                )
                slot.save()
        return super().destroy(request, *args, **kwargs)
