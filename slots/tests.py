import json
from datetime import datetime, timedelta

import pytz
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from .models import Slot
from .utils import create_time_slots


class SlotModelTest(TestCase):
    """슬롯 모델에 대한 테스트"""

    def setUp(self):
        """테스트용 슬롯 생성"""
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
        # 특정 날짜에 대한 슬롯 생성
        kst = pytz.timezone("Asia/Seoul")
        start_date_str = (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        count, slots = create_time_slots(start_date=start_date_str, days=1)

        # 1일 = 48개 슬롯 (30분 간격)
        self.assertEqual(count, 48)
        self.assertEqual(len(slots), 48)

        # 30분 간격 확인
        for i in range(1, len(slots)):
            time_diff = slots[i].slot_start_time - slots[i - 1].slot_start_time
            self.assertEqual(time_diff.total_seconds(), 30 * 60)  # 30분

        # 00분 또는 30분으로 끝나는지 확인
        for slot in slots:
            self.assertTrue(slot.slot_start_time.minute in [0, 30])
            self.assertTrue(slot.slot_end_time.minute in [0, 30])


class SlotAPITest(TestCase):
    """슬롯 API에 대한 테스트"""

    def setUp(self):
        """테스트용 슬롯 생성 및 클라이언트 설정"""
        self.client = Client()
        self.api_url = reverse("slot-list")

        # 오늘부터 3일치 슬롯 생성
        kst = pytz.timezone("Asia/Seoul")
        self.today = (
            timezone.now()
            .astimezone(kst)
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )
        count, self.slots = create_time_slots(start_date=self.today, days=3)

    def test_get_all_slots(self):
        """모든 슬롯 조회 테스트"""
        response = self.client.get(self.api_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        self.assertEqual(data["count"], len(self.slots))

    def test_filter_slots_by_date(self):
        """날짜로 슬롯 필터링 테스트"""
        date_str = self.today.strftime("%Y-%m-%d")
        response = self.client.get(f"{self.api_url}?date={date_str}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        # 하루에 48개 슬롯 (30분 간격)
        self.assertEqual(data["count"], 48)

    def test_filter_slots_by_time_range(self):
        """시간 범위로 슬롯 필터링 테스트"""
        start = self.today.strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (self.today + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M:%SZ")

        response = self.client.get(f"{self.api_url}?start={start}&end={end}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = json.loads(response.content)
        # 5시간 = 10개 슬롯 (30분 간격)
        self.assertEqual(data["count"], 10)
