from datetime import timedelta

import pytz
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from slots.models import Slot
from slots.utils import create_time_slots


class SlotModelTest(TestCase):
    """슬롯 모델에 대한 테스트"""

    def setUp(self):
        kst = pytz.timezone("Asia/Seoul")
        self.now = timezone.now().astimezone(kst)
        self.slot = Slot.objects.create(
            slot_start_time=self.now,
            slot_end_time=self.now + timedelta(minutes=30),
            capacity_used=1000,
        )

    def test_remaining_capacity(self):
        """슬롯의 남은 수용 인원 계산 테스트"""
        self.assertEqual(self.slot.remaining_capacity(), 50000 - 1000)

    def test_str_representation(self):
        """슬롯의 문자열 표현 테스트"""
        expected = f"{self.slot.slot_start_time.strftime('%Y-%m-%d %H:%M')} ~ {self.slot.slot_end_time.strftime('%H:%M')}"
        self.assertEqual(str(self.slot), expected)


class SlotUtilsTest(TestCase):
    """슬롯 유틸리티 함수에 대한 테스트"""

    def test_create_time_slots(self):
        """타임 슬롯 생성 유틸리티 테스트"""
        kst = pytz.timezone("Asia/Seoul")
        start_date_str = (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        count, slots = create_time_slots(start_date=start_date_str, days=1)
        self.assertEqual(count, 48)
        self.assertEqual(len(slots), 48)
        for i in range(1, len(slots)):
            time_diff = slots[i].slot_start_time - slots[i - 1].slot_start_time
            self.assertEqual(time_diff.total_seconds(), 30 * 60)
        for slot in slots:
            self.assertIn(slot.slot_start_time.minute, [0, 30])
            self.assertIn(slot.slot_end_time.minute, [0, 30])


class SlotAPITest(TestCase):
    """슬롯 API에 대한 테스트"""

    def setUp(self):
        self.client = APIClient()
        kst = pytz.timezone("Asia/Seoul")
        self.today = (
            timezone.now()
            .astimezone(kst)
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )
        # 오늘부터 3일치 슬롯 생성: 각 날짜에 대해 48개 슬롯
        start_date = self.today
        for day in range(3):
            day_date = start_date + timedelta(days=day)
            for hour in range(24):
                for minute in [0, 30]:
                    slot_start = day_date.replace(hour=hour, minute=minute)
                    slot_end = slot_start + timedelta(minutes=30)
                    Slot.objects.create(
                        slot_start_time=slot_start,
                        slot_end_time=slot_end,
                        capacity_used=0,
                    )
        self.slots = Slot.objects.filter(
            slot_start_time__gte=start_date,
            slot_start_time__lt=start_date + timedelta(days=3),
        ).order_by("slot_start_time")

    def test_available_dates(self):
        """한 달 내 예약 가능한 날짜 조회 API 테스트"""
        url = reverse("slot-available-dates")
        year = self.today.year
        month = self.today.month
        response = self.client.get(f"{url}?year={year}&month={month}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        same_month_dates = [
            (self.today + timedelta(days=day)).strftime("%Y-%m-%d")
            for day in range(3)
            if (self.today + timedelta(days=day)).month == month
        ]
        expected_dates_count = len(same_month_dates)
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), expected_dates_count)
        for item in data:
            self.assertIn("date", item)
            self.assertIn("available_slots_count", item)
            # 모든 슬롯은 가용하므로 하루 48개가 반환되어야 함
            self.assertEqual(item["available_slots_count"], 48)

    def test_available_day_slots(self):
        """특정 날짜의 예약 가능한 슬롯 조회 API 테스트"""
        url = reverse("slot-day-slots")
        date_str = self.today.strftime("%Y-%m-%d")
        response = self.client.get(f"{url}?date={date_str}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 48)

    def test_available_dates_with_invalid_query_params(self):
        """잘못된 year/month 파라미터가 들어왔을 때 400 응답을 반환하는지 테스트"""
        url = reverse("slot-available-dates")

        # year 누락
        response = self.client.get(f"{url}?month=4")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # month 누락
        response = self.client.get(f"{url}?year=2025")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # year, month 모두 누락
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # 잘못된 값 (음수, 문자열 등)
        response = self.client.get(f"{url}?year=abcd&month=4")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(f"{url}?year=2025&month=-1")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.get(f"{url}?year=2025&month=13")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_fully_booked_slot_excluded_from_available_dates(self):
        """
        confirm 후에 슬롯이 50,000명으로 꽉 차면,
        available_dates API에서 해당 슬롯이 집계에서 제외되는지 검증합니다.
        """
        # 완전히 꽉 찬 슬롯: 첫 번째 슬롯을 선택하고 capacity_used를 40000으로 설정
        slot = self.slots.first()
        slot.capacity_used = 40000
        slot.save()
        # 예약 확인 시 10000명이 추가되어 꽉 찬 상태(40000+10000=50000)
        # AvailableDatesAPIView에서 이 슬롯은 집계에서 제외되어야 함

        # confirm 전 available_dates API 호출
        url = reverse("slot-available-dates")
        year = self.today.year
        month = self.today.month
        response_before = self.client.get(f"{url}?year={year}&month={month}")
        data_before = response_before.json()
        # 해당 날짜에 슬롯 수(48) 중, 해당 슬롯이 포함되어 있으므로 count는 48
        self.assertEqual(data_before[0]["available_slots_count"], 48)

        # 이제 해당 슬롯을 confirm 처리하는 상황을 모의합니다.
        # (실제 confirm 액션은 ReservationViewSet에 있으므로, 여기서는 직접 슬롯 업데이트)
        slot.capacity_used = 50000
        slot.save()

        # confirm 후 available_dates API 호출
        response_after = self.client.get(f"{url}?year={year}&month={month}")
        data_after = response_after.json()
        # 이제 첫 번째 날짜의 available_slots_count가 47이어야 함.
        self.assertEqual(data_after[0]["available_slots_count"], 47)
