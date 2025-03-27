from rest_framework import permissions

from .models import Reservation


class IsAdminOrOwnReservation(permissions.BasePermission):
    """
    - 관리자(staff)는 모든 예약 접근/조작 가능
    - 일반 사용자는 자신의 예약만 접근 가능
    - 일반 사용자는 PENDING 상태의 예약만 수정 가능
    - confirm 액션은 관리자만 가능
    """

    def has_permission(self, request, view):
        # 인증되지 않은 사용자 접근 불가
        if not request.user.is_authenticated:
            return False

        # 목록/생성 등은 인증만 되면 OK
        if view.action in ["list", "create"]:
            return True

        return True  # 나머지는 has_object_permission에서 판단

    def has_object_permission(self, request, view, obj):
        # 관리자(staff)는 언제나 가능
        if request.user.is_staff:
            return True

        # confirm 액션은 관리자 전용
        if view.action == "confirm":
            return False

        # 일반 사용자 → 자기 자신의 예약만 접근 가능
        if obj.user != request.user:
            return False

        # 일반 사용자 → 수정(put/patch)은 PENDING 상태만 가능
        if view.action in ["update", "partial_update"]:
            return obj.status == Reservation.STATUS_PENDING

        # 삭제, 조회 등은 본인 소유이면 가능
        return True
