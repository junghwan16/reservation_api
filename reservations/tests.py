import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytz
from django.contrib.auth.models import User
from django.db import transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from slots.models import Slot
from slots.utils import create_time_slots

from .models import Reservation, ReservationSlot


class ReservationModelTest(TestCase):
    """예약 모델에 대한 테스트"""

    def setUp(self):
        """테스트용 슬롯과 예약 생성"""
        kst = pytz.timezone("Asia/Seoul")

        # 테스트용 사용자 생성
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        # 테스트용 슬롯 생성 (4일 후부터 시작)
        self.future_date = timezone.now() + timedelta(days=4)
        count, self.slots = create_time_slots(start_date=self.future_date, days=1)

        # 테스트용 예약 생성
        self.reservation = Reservation.objects.create(
            user=self.user, total_attendees=5000, status="PENDING"
        )

        # 첫 2시간 슬롯 연결 (1시간=2개 슬롯)
        for slot in self.slots[:4]:
            ReservationSlot.objects.create(reservation=self.reservation, slot=slot)

    def test_str_representation(self):
        """예약의 문자열 표현 테스트"""
        expected = f"Reservation #{self.reservation.id} - User: {self.user.username} - Status: PENDING"
        self.assertEqual(str(self.reservation), expected)

    def test_reservation_slots_relationship(self):
        """예약과 슬롯 간의 관계 테스트"""
        self.assertEqual(self.reservation.slots.count(), 4)

        # 예약이 올바른 슬롯에 연결되었는지 확인
        for i, slot in enumerate(self.slots[:4]):
            self.assertTrue(self.reservation.slots.filter(id=slot.id).exists())


class ReservationAPITest(TestCase):
    """예약 API에 대한 테스트"""

    def setUp(self):
        """테스트 클라이언트 설정 및 테스트용 슬롯과 사용자 생성"""
        self.client = APIClient()
        self.api_url = reverse("reservation-list")

        # 테스트용 슬롯 생성 (4일 후부터 시작하여 3일치)
        self.future_date = timezone.now() + timedelta(days=4)
        count, self.slots = create_time_slots(start_date=self.future_date, days=3)

        # 테스트용 관리자 생성
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass"
        )

        # 테스트용 일반 사용자 생성
        self.user = User.objects.create_user(
            username="user", email="user@example.com", password="userpass"
        )

        # 다른 테스트 사용자 생성
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="otherpass"
        )

    def get_tokens_for_user(self, user):
        """사용자에 대한 JWT 토큰 생성"""
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    def authenticate_as_user(self):
        """일반 사용자로 인증"""
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def authenticate_as_admin(self):
        """관리자로 인증"""
        tokens = self.get_tokens_for_user(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def authenticate_as_other_user(self):
        """다른 사용자로 인증"""
        tokens = self.get_tokens_for_user(self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_create_reservation(self):
        """예약 생성 테스트"""
        # 사용자로 인증
        self.authenticate_as_user()

        data = {
            "total_attendees": 1000,
            "slot_ids": [self.slots[0].id, self.slots[1].id],
        }

        response = self.client.post(
            self.api_url,
            data=json.dumps(data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 예약이 정상적으로 생성되었는지 확인
        reservation_id = response.data["id"]
        reservation = Reservation.objects.get(id=reservation_id)

        self.assertEqual(reservation.user, self.user)
        self.assertEqual(reservation.total_attendees, 1000)
        self.assertEqual(reservation.status, "PENDING")
        self.assertEqual(reservation.slots.count(), 2)

    def test_create_reservation_with_user(self):
        """인증된 사용자로 예약 생성 테스트"""
        # 사용자로 인증
        self.authenticate_as_user()

        data = {
            "user": self.other_user.id,  # 다른 사용자 ID 지정 시도
            "total_attendees": 1000,
            "slot_ids": [self.slots[0].id, self.slots[1].id],
        }

        response = self.client.post(
            self.api_url,
            data=json.dumps(data),
            content_type="application/json",
        )

        # 항상 현재 인증된 사용자의 ID로 생성되어야 함
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 예약이 현재 인증된 사용자로 생성되었는지 확인
        reservation_id = response.data["id"]
        reservation = Reservation.objects.get(id=reservation_id)
        self.assertEqual(reservation.user, self.user)

    def test_reservation_validation_with_invalid_slot(self):
        """3일 이내 시작하는 슬롯으로 예약 생성 시 검증 실패 테스트"""
        # 사용자로 인증
        self.authenticate_as_user()

        # 오늘부터 시작하는 슬롯 생성 (3일 제한에 걸리도록)
        count, near_slots = create_time_slots(days=1)

        data = {
            "total_attendees": 1000,
            "slot_ids": [near_slots[0].id],
        }

        response = self.client.post(
            self.api_url,
            data=json.dumps(data),
            content_type="application/json",
        )

        # 검증 오류로 400 Bad Request 예상
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_reservation(self):
        """예약 수정 테스트"""
        # 사용자로 인증
        self.authenticate_as_user()

        # 먼저 예약 생성
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="PENDING"
        )

        # 슬롯 연결
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 수정 데이터
        update_data = {
            "total_attendees": 2000,
            "slot_ids": [self.slots[2].id, self.slots[3].id],  # 다른 슬롯으로 변경
        }

        # 수정 요청
        update_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.patch(
            update_url,
            data=json.dumps(update_data),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 변경 사항 확인
        reservation.refresh_from_db()
        self.assertEqual(reservation.total_attendees, 2000)
        self.assertEqual(reservation.slots.count(), 2)
        self.assertTrue(reservation.slots.filter(id=self.slots[2].id).exists())

    def test_update_confirmed_reservation(self):
        """확정된 예약 수정 시도 테스트"""
        # 사용자로 인증
        self.authenticate_as_user()

        # 확정된 예약 생성
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="CONFIRMED"
        )

        # 슬롯 연결
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 수정 데이터
        update_data = {
            "total_attendees": 2000,
        }

        # 수정 요청
        update_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.patch(
            update_url,
            data=json.dumps(update_data),
            content_type="application/json",
        )

        # 확정된 예약은 수정 불가능하므로 400 Bad Request 예상
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_reservation(self):
        """예약 확정 테스트 (관리자)"""
        # 먼저 예약 생성
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="PENDING"
        )

        # 슬롯 연결
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 관리자로 인증
        self.authenticate_as_admin()

        # 예약 확정 요청
        confirm_url = reverse("reservation-confirm", args=[reservation.id])
        response = self.client.post(confirm_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 예약 상태가 CONFIRMED로 변경되었는지 확인
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "CONFIRMED")

        # 슬롯의 capacity_used가 업데이트되었는지 확인
        for slot in self.slots[:2]:
            slot.refresh_from_db()
            self.assertEqual(slot.capacity_used, 1000)

    def test_confirm_reservation_by_non_admin(self):
        """일반 사용자가 예약 확정 시도 테스트"""
        # 예약 생성
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="PENDING"
        )

        # 슬롯 연결
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 일반 사용자로 인증
        self.authenticate_as_user()

        # 예약 확정 요청
        confirm_url = reverse("reservation-confirm", args=[reservation.id])
        response = self.client.post(confirm_url)

        # 권한 오류로 403 Forbidden 예상
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # 예약 상태가 변경되지 않았는지 확인
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "PENDING")

    def test_capacity_validation_when_confirming(self):
        """확정 시 수용 인원 초과 검증 테스트"""
        # 관리자로 인증
        self.authenticate_as_admin()

        # 슬롯에 이미 40,000명이 예약됨
        slot = self.slots[0]
        slot.capacity_used = 40000
        slot.save()

        # 새 예약 생성 (15,000명 - 초과하도록)
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=15000, status="PENDING"
        )

        # 슬롯 연결
        ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 예약 확정 요청
        confirm_url = reverse("reservation-confirm", args=[reservation.id])
        response = self.client.post(confirm_url)

        # 수용 인원 초과로 400 Bad Request 예상
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 예약 상태가 여전히 PENDING인지 확인
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "PENDING")

        # 슬롯의 capacity_used가 변하지 않았는지 확인
        slot.refresh_from_db()
        self.assertEqual(slot.capacity_used, 40000)

    def test_delete_confirmed_reservation(self):
        """확정된 예약 삭제 테스트"""
        # 사용자로 인증
        self.authenticate_as_user()

        # 먼저 예약 생성하고 확정
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=2000, status="CONFIRMED"
        )

        # 슬롯 연결
        slot = self.slots[0]
        slot.capacity_used = 2000  # 예약 인원만큼 설정
        slot.save()

        ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 예약 삭제 요청
        delete_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.delete(delete_url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # 슬롯의 capacity_used가 감소했는지 확인
        slot.refresh_from_db()
        self.assertEqual(slot.capacity_used, 0)

        # 예약이 삭제되었는지 확인
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_other_user_reservation(self):
        """다른 사용자의 예약 삭제 시도 테스트"""
        # 일반 사용자로 인증
        self.authenticate_as_user()

        # 다른 사용자의 예약 생성
        reservation = Reservation.objects.create(
            user=self.other_user, total_attendees=1000, status="PENDING"
        )

        # 슬롯 연결
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)

        # 삭제 요청 (다른 사용자의 예약)
        delete_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.delete(delete_url)

        # 권한 오류로 403 또는 404 예상 (서버 구현에 따라 다를 수 있음)
        self.assertIn(
            response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )

        # 예약이 삭제되지 않았는지 확인
        self.assertTrue(Reservation.objects.filter(id=reservation.id).exists())

    def test_list_own_reservations(self):
        """자신의 예약 목록 조회 테스트"""
        # 일반 사용자로 인증
        self.authenticate_as_user()

        # 기존 데이터를 모두 삭제하여 정확한 테스트 환경 구성
        Reservation.objects.all().delete()

        # 현재 사용자로 예약 생성
        for i in range(3):
            reservation = Reservation.objects.create(
                user=self.user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])

        # 다른 사용자로 예약 생성
        for i in range(2):
            reservation = Reservation.objects.create(
                user=self.other_user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])

        # 예약 목록 조회
        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 본인의 예약만 조회되는지 확인
        data = response.json()
        self.assertIsNotNone(data["results"])

        # 페이지네이션 적용되어 있어 results 내에 항목이 있는지 확인
        self.assertEqual(len(data["results"]), 3)  # 사용자 자신의 예약만 3개

        # 모든 예약이 현재 사용자의 것인지 확인
        for reservation in data["results"]:
            self.assertEqual(reservation["user"], self.user.id)

    def test_admin_list_all_reservations(self):
        """관리자의 모든 예약 목록 조회 테스트"""
        # 관리자로 인증
        self.authenticate_as_admin()

        # 기존 데이터 삭제 후 정확한 테스트
        Reservation.objects.all().delete()

        # 일반 사용자로 예약 생성
        for i in range(3):
            reservation = Reservation.objects.create(
                user=self.user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])

        # 다른 사용자로 예약 생성
        for i in range(2):
            reservation = Reservation.objects.create(
                user=self.other_user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])

        # 예약 목록 조회
        response = self.client.get(self.api_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 관리자는 모든 예약을 조회할 수 있어야 함
        data = response.json()
        self.assertIsNotNone(data["results"])

        # 총 5개의 예약이 있어야 함
        self.assertEqual(len(data["results"]), 5)


class ReservationConcurrencyTest(TransactionTestCase):
    """예약 동시성에 대한 테스트"""

    def setUp(self):
        """테스트 설정"""
        # 테스트용 사용자 생성
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )

        # 테스트용 슬롯 생성 (4일 후부터 시작)
        self.future_date = timezone.now() + timedelta(days=4)
        count, self.slots = create_time_slots(start_date=self.future_date, days=1)

        # 테스트 슬롯에 초기 용량 설정
        self.slot = self.slots[0]
        self.slot.capacity_used = 30000
        self.slot.save()

        # 관리자 생성
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass"
        )

    def get_tokens_for_user(self, user):
        """사용자에 대한 JWT 토큰 생성"""
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    @patch("django.db.transaction.on_commit")
    def test_confirm_reservations_concurrently(self, mock_on_commit):
        """여러 예약을 동시에 확정할 때 비관적 락 테스트"""
        # on_commit을 즉시 실행하도록 모킹
        mock_on_commit.side_effect = lambda func: func()

        # 첫 번째 예약 생성 (10,000명)
        reservation1 = Reservation.objects.create(
            user=self.user, total_attendees=10000, status="PENDING"
        )
        ReservationSlot.objects.create(reservation=reservation1, slot=self.slot)

        # 두 번째 예약 생성 (5,000명)
        other_user = User.objects.create_user(
            username="other", email="other@example.com", password="otherpass"
        )
        reservation2 = Reservation.objects.create(
            user=other_user, total_attendees=5000, status="PENDING"
        )
        ReservationSlot.objects.create(reservation=reservation2, slot=self.slot)

        # 관리자 클라이언트 준비
        admin_client = APIClient()
        tokens = self.get_tokens_for_user(self.admin_user)
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 첫 번째 예약 확정 요청
        confirm_url1 = reverse("reservation-confirm", args=[reservation1.id])

        # 두 번째 예약 확정 요청
        confirm_url2 = reverse("reservation-confirm", args=[reservation2.id])

        # 첫 번째 예약 확정 진행
        with transaction.atomic():
            response1 = admin_client.post(confirm_url1)
            self.assertEqual(response1.status_code, status.HTTP_200_OK)

            # 슬롯 용량 업데이트 확인
            self.slot.refresh_from_db()
            self.assertEqual(self.slot.capacity_used, 40000)

            # 두 번째 예약 확정 진행
            response2 = admin_client.post(confirm_url2)

            # 첫 번째 예약으로 인해 용량이 40,000이 되었으므로 두 번째 예약(5,000)은 성공해야함
            self.assertEqual(response2.status_code, status.HTTP_200_OK)

            # 슬롯 용량 최종 업데이트 확인
            self.slot.refresh_from_db()
            self.assertEqual(self.slot.capacity_used, 45000)

    @patch("django.db.transaction.on_commit")
    def test_confirm_reservation_capacity_race_condition(self, mock_on_commit):
        """용량 제한에 도달할 때 경쟁 상태 테스트"""
        # on_commit을 즉시 실행하도록 모킹
        mock_on_commit.side_effect = lambda func: func()

        # 첫 번째 예약 생성 (15,000명)
        reservation1 = Reservation.objects.create(
            user=self.user, total_attendees=15000, status="PENDING"
        )
        ReservationSlot.objects.create(reservation=reservation1, slot=self.slot)

        # 두 번째 예약 생성 (10,000명)
        other_user = User.objects.create_user(
            username="other2", email="other2@example.com", password="otherpass"
        )
        reservation2 = Reservation.objects.create(
            user=other_user, total_attendees=10000, status="PENDING"
        )
        ReservationSlot.objects.create(reservation=reservation2, slot=self.slot)

        # 관리자 클라이언트 준비
        admin_client = APIClient()
        tokens = self.get_tokens_for_user(self.admin_user)
        admin_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # 테스트 슬롯 용량을 45,000으로 설정 (5,000 남음)
        self.slot.capacity_used = 45000
        self.slot.save()

        # 첫 번째 예약 확정 요청
        confirm_url1 = reverse("reservation-confirm", args=[reservation1.id])

        # 두 번째 예약 확정 요청
        confirm_url2 = reverse("reservation-confirm", args=[reservation2.id])

        # 첫 번째 예약(15,000명) 확정 시도 - 용량 초과로 실패해야 함
        response1 = admin_client.post(confirm_url1)
        self.assertEqual(response1.status_code, status.HTTP_400_BAD_REQUEST)

        # 두 번째 예약(10,000명) 확정 시도 - 용량(5,000) 초과로 실패해야 함
        response2 = admin_client.post(confirm_url2)
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

        # 슬롯 용량이 변경되지 않았는지 확인
        self.slot.refresh_from_db()
        self.assertEqual(self.slot.capacity_used, 45000)
