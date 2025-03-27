import calendar
from datetime import datetime, timedelta
from typing import List, Optional, Tuple, Union

import pytz
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Slot


def create_time_slots(
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
    days: int = 30,
    batch_size: int = 100,
) -> Tuple[int, List[Slot]]:
    """
    KST 기준으로 30분 간격의 슬롯을 생성합니다.

    Args:
        start_date: 시작 날짜 (YYYY-MM-DD 문자열 또는 datetime 객체). None이면 오늘부터.
        end_date: 종료 날짜 (YYYY-MM-DD 문자열 또는 datetime 객체). None이면 시작일로부터 days일.
        days: 생성할 일수 (기본 30일).
        batch_size: 일괄 생성할 슬롯 수.

    Returns:
        (생성된 슬롯 수, 생성된 Slot 객체 리스트)
    """
    kst = pytz.timezone("Asia/Seoul")
    start_date = _normalize_date(start_date, kst, is_start=True)
    end_date = _normalize_date(
        end_date, kst, is_start=False, start_date=start_date, days=days
    )
    slot_times = _generate_slot_times(start_date, end_date)
    return _create_slots_in_batches(slot_times, batch_size)


def _normalize_date(
    date_value: Optional[Union[str, datetime]],
    tz: pytz.timezone,
    is_start: bool = True,
    start_date: Optional[datetime] = None,
    days: int = 30,
) -> datetime:
    """
    날짜 값을 지정된 시간대로 정규화합니다.

    Args:
        date_value: 날짜 (문자열 또는 datetime)
        tz: 시간대 (예: pytz.timezone("Asia/Seoul"))
        is_start: 시작 날짜이면 True, 종료 날짜이면 False.
        start_date: 종료 날짜를 계산할 때 기준이 되는 시작 날짜.
        days: 종료 날짜 계산 시 사용할 일수.

    Returns:
        정규화된 datetime 객체.
    """
    if date_value:
        if isinstance(date_value, str):
            date_obj = datetime.strptime(date_value, "%Y-%m-%d")
            date_obj = date_obj.replace(
                hour=0 if is_start else 23,
                minute=0 if is_start else 59,
                second=0 if is_start else 59,
                microsecond=0 if is_start else 999999,
            )
            date_obj = tz.localize(date_obj)
        elif isinstance(date_value, datetime):
            if timezone.is_naive(date_value):
                date_obj = tz.localize(date_value)
            else:
                date_obj = date_value.astimezone(tz)
            date_obj = date_obj.replace(
                hour=0 if is_start else 23,
                minute=0 if is_start else 59,
                second=0 if is_start else 59,
                microsecond=0 if is_start else 999999,
            )
    else:
        if is_start:
            date_obj = (
                timezone.now()
                .astimezone(tz)
                .replace(hour=0, minute=0, second=0, microsecond=0)
            )
        else:
            date_obj = start_date + timedelta(days=days) - timedelta(microseconds=1)
    return date_obj


def _generate_slot_times(
    start_date: datetime, end_date: datetime
) -> List[Tuple[datetime, datetime]]:
    """
    주어진 기간 동안 30분 간격의 슬롯 (시작, 종료) 튜플 목록을 생성합니다.
    """
    slot_times = []
    current_time = start_date
    while current_time <= end_date:
        minute = 0 if current_time.minute < 30 else 30
        current_time = current_time.replace(minute=minute, second=0, microsecond=0)
        slot_end_time = current_time + timedelta(minutes=30)
        slot_times.append((current_time, slot_end_time))
        current_time += timedelta(minutes=30)
    return slot_times


@transaction.atomic
def _create_slots_in_batches(
    slot_times: List[Tuple[datetime, datetime]], batch_size: int
) -> Tuple[int, List[Slot]]:
    """
    존재하지 않는 슬롯만 일괄 생성합니다.
    """
    existing_slots_filter = Q()
    for start_time, end_time in slot_times:
        existing_slots_filter |= Q(slot_start_time=start_time, slot_end_time=end_time)
    if existing_slots_filter:
        existing_slots = set(
            Slot.objects.filter(existing_slots_filter).values_list(
                "slot_start_time", "slot_end_time"
            )
        )
    else:
        existing_slots = set()

    slots_to_create = [
        Slot(slot_start_time=start_time, slot_end_time=end_time)
        for start_time, end_time in slot_times
        if (start_time, end_time) not in existing_slots
    ]

    created_slots = []
    total_created = 0
    for i in range(0, len(slots_to_create), batch_size):
        batch = slots_to_create[i : i + batch_size]
        batch_created = Slot.objects.bulk_create(batch)
        created_slots.extend(batch_created)
        total_created += len(batch_created)
    return total_created, created_slots


def get_day_start_end(date: datetime.date) -> Tuple[datetime, datetime]:
    """
    주어진 날짜의 시작(00:00:00)과 종료(23:59:59) 시간을 반환합니다.
    """
    tz = timezone.get_current_timezone()
    start_datetime = timezone.datetime.combine(date, datetime.min.time(), tzinfo=tz)
    end_datetime = timezone.datetime.combine(date, datetime.max.time(), tzinfo=tz)
    return start_datetime, end_datetime


def get_month_range(year: int, month: int) -> Tuple[datetime, datetime]:
    """
    주어진 연도와 월의 시작일과 종료일을 반환합니다.
    """
    tz = timezone.get_current_timezone()
    start_date = timezone.datetime(year, month, 1, tzinfo=tz)
    last_day = calendar.monthrange(year, month)[1]
    end_date = timezone.datetime(year, month, last_day, 23, 59, 59, tzinfo=tz)
    return start_date, end_date
