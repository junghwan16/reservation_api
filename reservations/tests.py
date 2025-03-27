import json
from datetime import timedelta

import pytz
from django.contrib.auth.models import User
from django.test import TestCase
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
        kst = pytz.timezone("Asia/Seoul")
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass"
        )
        self.future_date = timezone.now() + timedelta(days=4)
        count, self.slots = create_time_slots(start_date=self.future_date, days=1)
        self.reservation = Reservation.objects.create(
            user=self.user, total_attendees=5000, status="PENDING"
        )
        for slot in self.slots[:4]:
            ReservationSlot.objects.create(reservation=self.reservation, slot=slot)

    def test_str_representation(self):
        expected = f"Reservation #{self.reservation.id} - User: {self.user.username} - Status: PENDING"
        self.assertEqual(str(self.reservation), expected)

    def test_reservation_slots_relationship(self):
        self.assertEqual(self.reservation.slots.count(), 4)
        for slot in self.slots[:4]:
            self.assertTrue(self.reservation.slots.filter(id=slot.id).exists())


class ReservationAPITest(TestCase):
    """예약 API에 대한 테스트"""

    def setUp(self):
        self.client = APIClient()
        self.api_url = reverse("reservation-list")
        self.future_date = timezone.now() + timedelta(days=4)
        count, self.slots = create_time_slots(start_date=self.future_date, days=3)
        self.admin_user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass"
        )
        self.user = User.objects.create_user(
            username="user", email="user@example.com", password="userpass"
        )
        self.other_user = User.objects.create_user(
            username="otheruser", email="other@example.com", password="otherpass"
        )

    def get_tokens_for_user(self, user):
        refresh = RefreshToken.for_user(user)
        return {"refresh": str(refresh), "access": str(refresh.access_token)}

    def authenticate_as_user(self):
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def authenticate_as_admin(self):
        tokens = self.get_tokens_for_user(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def authenticate_as_other_user(self):
        tokens = self.get_tokens_for_user(self.other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

    def test_create_reservation(self):
        """예약 생성 테스트 - 정상 케이스"""
        self.authenticate_as_user()
        data = {
            "total_attendees": 1000,
            "slot_ids": [self.slots[0].id, self.slots[1].id],
        }
        response = self.client.post(
            self.api_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reservation = Reservation.objects.get(id=response.data["id"])
        self.assertEqual(reservation.user, self.user)
        self.assertEqual(reservation.total_attendees, 1000)
        self.assertEqual(reservation.status, "PENDING")
        self.assertEqual(reservation.slots.count(), 2)

    def test_create_reservation_with_user_override(self):
        """예약 생성 시 입력된 user 필드는 무시되어 현재 인증된 사용자로 생성됨"""
        self.authenticate_as_user()
        data = {
            "user": self.other_user.id,
            "total_attendees": 1000,
            "slot_ids": [self.slots[0].id, self.slots[1].id],
        }
        response = self.client.post(
            self.api_url, data=json.dumps(data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reservation = Reservation.objects.get(id=response.data["id"])
        self.assertEqual(reservation.user, self.user)

    def test_reservation_validation_with_invalid_slot(self):
        """3일 이내 시작하는 슬롯으로 예약 생성 시 검증 실패 테스트"""
        self.authenticate_as_user()
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
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("72시간 이내", response.data["slot_ids"][0])

    def test_update_reservation(self):
        """예약 수정 테스트 (PENDING 상태)"""
        self.authenticate_as_user()
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="PENDING"
        )
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)
        update_data = {
            "total_attendees": 2000,
            "slot_ids": [self.slots[2].id, self.slots[3].id],
        }
        update_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.patch(
            update_url, data=json.dumps(update_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reservation.refresh_from_db()
        self.assertEqual(reservation.total_attendees, 2000)
        self.assertEqual(reservation.slots.count(), 2)
        self.assertTrue(reservation.slots.filter(id=self.slots[2].id).exists())

    def test_update_confirmed_reservation(self):
        """일반 사용자가 CONFIRMED 예약 수정 시도시 실패해야 함"""
        self.authenticate_as_user()
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="CONFIRMED"
        )
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)
        update_data = {"total_attendees": 2000}
        update_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.patch(
            update_url, data=json.dumps(update_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_confirm_reservation(self):
        """예약 확정 테스트 (관리자)"""
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="PENDING"
        )
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)
        self.authenticate_as_admin()
        confirm_url = reverse("reservation-confirm", args=[reservation.id])
        response = self.client.post(confirm_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "CONFIRMED")
        for slot in self.slots[:2]:
            slot.refresh_from_db()
            self.assertEqual(slot.capacity_used, 1000)

    def test_confirm_reservation_by_non_admin(self):
        """일반 사용자가 예약 확정 시도하면 권한 에러 발생"""
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="PENDING"
        )
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)
        self.authenticate_as_user()
        confirm_url = reverse("reservation-confirm", args=[reservation.id])
        response = self.client.post(confirm_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "PENDING")

    def test_capacity_validation_when_confirming(self):
        """예약 확정 시 슬롯 capacity 초과 여부 검증 테스트"""
        self.authenticate_as_admin()
        slot = self.slots[0]
        slot.capacity_used = 40000
        slot.save()
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=15000, status="PENDING"
        )
        ReservationSlot.objects.create(reservation=reservation, slot=slot)
        confirm_url = reverse("reservation-confirm", args=[reservation.id])
        response = self.client.post(confirm_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, "PENDING")
        slot.refresh_from_db()
        self.assertEqual(slot.capacity_used, 40000)

    def test_delete_confirmed_reservation(self):
        """확정된 예약 삭제 시 슬롯 capacity 복구 확인 테스트"""
        self.authenticate_as_user()
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=2000, status="CONFIRMED"
        )
        slot = self.slots[0]
        slot.capacity_used = 2000
        slot.save()
        ReservationSlot.objects.create(reservation=reservation, slot=slot)
        delete_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.delete(delete_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        slot.refresh_from_db()
        self.assertEqual(slot.capacity_used, 0)
        self.assertFalse(Reservation.objects.filter(id=reservation.id).exists())

    def test_delete_other_user_reservation(self):
        """다른 사용자의 예약 삭제 시 권한 오류 발생 테스트"""
        self.authenticate_as_user()
        reservation = Reservation.objects.create(
            user=self.other_user, total_attendees=1000, status="PENDING"
        )
        for slot in self.slots[:2]:
            ReservationSlot.objects.create(reservation=reservation, slot=slot)
        delete_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.delete(delete_url)
        self.assertIn(
            response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]
        )
        self.assertTrue(Reservation.objects.filter(id=reservation.id).exists())

    def test_list_own_reservations(self):
        """일반 사용자가 자신의 예약 목록만 조회하는지 테스트"""
        self.authenticate_as_user()
        Reservation.objects.all().delete()
        for i in range(3):
            reservation = Reservation.objects.create(
                user=self.user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])
        for i in range(2):
            reservation = Reservation.objects.create(
                user=self.other_user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsNotNone(data["results"])
        self.assertEqual(len(data["results"]), 3)
        for reservation in data["results"]:
            self.assertEqual(reservation["user"], self.user.id)

    def test_admin_list_all_reservations(self):
        """관리자가 모든 예약 목록을 조회하는지 테스트"""
        self.authenticate_as_admin()
        Reservation.objects.all().delete()
        for i in range(3):
            reservation = Reservation.objects.create(
                user=self.user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])
        for i in range(2):
            reservation = Reservation.objects.create(
                user=self.other_user, total_attendees=1000, status="PENDING"
            )
            ReservationSlot.objects.create(reservation=reservation, slot=self.slots[i])
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIsNotNone(data["results"])
        self.assertEqual(len(data["results"]), 5)

    def test_admin_update_confirmed_reservation(self):
        """관리자가 CONFIRMED 예약을 수정할 수 있는지 테스트"""
        self.authenticate_as_admin()
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="CONFIRMED"
        )
        slot = self.slots[0]
        slot.capacity_used = 1000
        slot.save()
        ReservationSlot.objects.create(reservation=reservation, slot=slot)
        update_data = {
            "total_attendees": 2000,
            "slot_ids": [self.slots[1].id],
        }
        update_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.patch(
            update_url, data=json.dumps(update_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        reservation.refresh_from_db()
        self.assertEqual(reservation.total_attendees, 2000)
        self.assertEqual(reservation.slots.count(), 1)
        self.assertTrue(reservation.slots.filter(id=self.slots[1].id).exists())
        slot.refresh_from_db()
        self.assertEqual(slot.capacity_used, 0)
        new_slot = self.slots[1]
        new_slot.refresh_from_db()
        self.assertEqual(new_slot.capacity_used, 2000)

    def test_admin_update_confirmed_reservation_capacity_exceed(self):
        """관리자가 CONFIRMED 예약 수정 시 슬롯 용량 초과면 에러 발생하는지 테스트"""
        self.authenticate_as_admin()
        reservation = Reservation.objects.create(
            user=self.user, total_attendees=1000, status="CONFIRMED"
        )
        slot = self.slots[0]
        slot.capacity_used = 1000
        slot.save()
        ReservationSlot.objects.create(reservation=reservation, slot=slot)
        target_slot = self.slots[1]
        target_slot.capacity_used = 45000
        target_slot.save()
        update_data = {
            "total_attendees": 10000,
            "slot_ids": [target_slot.id],
        }
        update_url = reverse("reservation-detail", args=[reservation.id])
        response = self.client.patch(
            update_url, data=json.dumps(update_data), content_type="application/json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        reservation.refresh_from_db()
        self.assertEqual(reservation.total_attendees, 1000)
        self.assertEqual(reservation.slots.count(), 1)
        self.assertTrue(reservation.slots.filter(id=slot.id).exists())
        slot.refresh_from_db()
        self.assertEqual(slot.capacity_used, 1000)
        target_slot.refresh_from_db()
        self.assertEqual(target_slot.capacity_used, 45000)
