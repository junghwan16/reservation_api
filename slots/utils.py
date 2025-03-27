from datetime import datetime, timedelta

import pytz
from django.utils import timezone

from .models import Slot


def create_time_slots(start_date=None, end_date=None, days=30):
    """
    KST 기준으로 30분 간격의 슬롯을 생성합니다.

    Args:
        start_date (str, optional): 시작 날짜 (YYYY-MM-DD 형식). None인 경우 오늘부터.
        end_date (str, optional): 종료 날짜 (YYYY-MM-DD 형식). None인 경우 시작일로부터 days일.
        days (int, optional): 생성할 일수 (기본값: 30일). start_date가 지정되고 end_date가 None인 경우에만 사용.

    Returns:
        tuple: (생성된 슬롯 수, 생성된 슬롯 리스트)
    """
    kst = pytz.timezone("Asia/Seoul")

    # 시작 날짜 설정
    if start_date:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").replace(
                hour=0, minute=0, second=0
            )
            start_date = kst.localize(start_date)
        # datetime 객체인 경우 timezone 확인
        elif isinstance(start_date, datetime):
            if timezone.is_naive(start_date):
                start_date = kst.localize(start_date)
            else:
                start_date = start_date.astimezone(kst)
            start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # 기본값: 오늘부터
        start_date = (
            timezone.now()
            .astimezone(kst)
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )

    # 종료 날짜 설정
    if end_date:
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59
            )
            end_date = kst.localize(end_date)
        # datetime 객체인 경우 timezone 확인
        elif isinstance(end_date, datetime):
            if timezone.is_naive(end_date):
                end_date = kst.localize(end_date)
            else:
                end_date = end_date.astimezone(kst)
            end_date = end_date.replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        # 기본값: 시작일 + days일
        end_date = start_date + timedelta(days=days) - timedelta(seconds=1)

    # 30분 간격으로 슬롯 생성
    current_time = start_date
    slot_count = 0
    created_slots = []

    while current_time <= end_date:
        # 30분 단위로 맞추기 (00분 또는 30분)
        minute = 0 if current_time.minute < 30 else 30
        current_time = current_time.replace(minute=minute, second=0, microsecond=0)

        slot_end_time = current_time + timedelta(minutes=30)

        # 이미 존재하는 슬롯인지 확인
        if not Slot.objects.filter(
            slot_start_time=current_time, slot_end_time=slot_end_time
        ).exists():
            slot = Slot.objects.create(
                slot_start_time=current_time, slot_end_time=slot_end_time
            )
            created_slots.append(slot)
            slot_count += 1

        current_time += timedelta(minutes=30)

    return slot_count, created_slots
