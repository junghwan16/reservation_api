from datetime import datetime, timedelta
from typing import List, Tuple, Union, Optional

import pytz
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Slot


def create_time_slots(
    start_date: Optional[Union[str, datetime]] = None,
    end_date: Optional[Union[str, datetime]] = None,
    days: int = 30,
    batch_size: int = 100
) -> Tuple[int, List[Slot]]:
    """
    KST 기준으로 30분 간격의 슬롯을 생성합니다.
    
    Args:
        start_date: 시작 날짜 (YYYY-MM-DD 형식 문자열 또는 datetime 객체). None인 경우 오늘부터.
        end_date: 종료 날짜 (YYYY-MM-DD 형식 문자열 또는 datetime 객체). None인 경우 시작일로부터 days일.
        days: 생성할 일수 (기본값: 30일). start_date가 지정되고 end_date가 None인 경우에만 사용.
        batch_size: 일괄 처리할 슬롯의 수 (기본값: 100).
    
    Returns:
        슬롯 생성 결과: (생성된 슬롯 수, 생성된 슬롯 리스트)
        
    Examples:
        >>> create_time_slots('2025-04-01', '2025-04-30')  # 4월 1일부터 30일까지 슬롯 생성
        >>> create_time_slots(None, None, days=7)  # 오늘부터 7일간의 슬롯 생성
    """
    kst = pytz.timezone("Asia/Seoul")
    
    # 시작 날짜 처리
    start_date = _normalize_date(start_date, kst, is_start=True)
    
    # 종료 날짜 처리
    end_date = _normalize_date(end_date, kst, is_start=False, start_date=start_date, days=days)
    
    # 30분 간격으로 슬롯 시간 생성
    slot_times = _generate_slot_times(start_date, end_date)
    
    # 이미 존재하는 슬롯 필터링 및 일괄 생성
    return _create_slots_in_batches(slot_times, batch_size)


def _normalize_date(
    date_value: Optional[Union[str, datetime]], 
    tz: pytz.timezone, 
    is_start: bool = True,
    start_date: Optional[datetime] = None, 
    days: int = 30
) -> datetime:
    """
    날짜 값을 지정된 시간대의 정규화된 datetime 객체로 변환합니다.
    
    Args:
        date_value: 변환할 날짜 (문자열 또는 datetime)
        tz: 시간대
        is_start: 시작 날짜인지 여부 (True: 0시 0분, False: 23시 59분)
        start_date: 시작 날짜 (end_date가 None이고 days가 지정된 경우 사용)
        days: 일수 (end_date가 None인 경우 사용)
    
    Returns:
        정규화된 datetime 객체
    """
    if date_value:
        if isinstance(date_value, str):
            # 문자열을 datetime으로 변환
            date_obj = datetime.strptime(date_value, "%Y-%m-%d")
            
            # 시작/종료일 여부에 따라 시간 설정
            if is_start:
                date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                date_obj = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
                
            # 시간대 설정
            date_obj = tz.localize(date_obj)
        
        elif isinstance(date_value, datetime):
            # 시간대 정규화
            if timezone.is_naive(date_value):
                date_obj = tz.localize(date_value)
            else:
                date_obj = date_value.astimezone(tz)
            
            # 시작/종료일 여부에 따라 시간 설정
            if is_start:
                date_obj = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
            else:
                date_obj = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        # 기본값 설정
        if is_start:
            # 시작일 기본값: 오늘
            date_obj = timezone.now().astimezone(tz).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            # 종료일 기본값: 시작일 + days일 - 1초
            date_obj = start_date + timedelta(days=days) - timedelta(microseconds=1)
    
    return date_obj


def _generate_slot_times(start_date: datetime, end_date: datetime) -> List[Tuple[datetime, datetime]]:
    """
    주어진 시작일과 종료일 사이의 모든 30분 슬롯 시간을 생성합니다.
    
    Args:
        start_date: 시작 날짜/시간
        end_date: 종료 날짜/시간
    
    Returns:
        슬롯 시간 목록 [(시작 시간, 종료 시간), ...]
    """
    slot_times = []
    current_time = start_date
    
    while current_time <= end_date:
        # 30분 단위로 맞추기 (00분 또는 30분)
        minute = 0 if current_time.minute < 30 else 30
        current_time = current_time.replace(minute=minute, second=0, microsecond=0)
        slot_end_time = current_time + timedelta(minutes=30)
        
        # 슬롯 시간 추가
        slot_times.append((current_time, slot_end_time))
        
        # 다음 슬롯으로 이동
        current_time += timedelta(minutes=30)
    
    return slot_times


@transaction.atomic
def _create_slots_in_batches(
    slot_times: List[Tuple[datetime, datetime]], 
    batch_size: int
) -> Tuple[int, List[Slot]]:
    """
    주어진 슬롯 시간에 대해 존재하지 않는 슬롯만 일괄 생성합니다.
    
    Args:
        slot_times: 슬롯 시간 목록 [(시작 시간, 종료 시간), ...]
        batch_size: 일괄 처리할 슬롯의 수
    
    Returns:
        (생성된 슬롯 수, 생성된 슬롯 리스트)
    """
    # 이미 존재하는 슬롯 필터링을 위한 조건 생성
    existing_slots_filter = Q()
    for start_time, end_time in slot_times:
        existing_slots_filter |= Q(slot_start_time=start_time, slot_end_time=end_time)
    
    # 이미 존재하는 슬롯 조회
    if existing_slots_filter:
        existing_slots = set(
            Slot.objects.filter(existing_slots_filter).values_list('slot_start_time', 'slot_end_time')
        )
    else:
        existing_slots = set()
    
    # 생성할 슬롯 필터링 및 객체 준비
    slots_to_create = []
    created_slots = []
    
    for start_time, end_time in slot_times:
        if (start_time, end_time) not in existing_slots:
            slots_to_create.append(
                Slot(slot_start_time=start_time, slot_end_time=end_time)
            )
    
    # 일괄 처리로 슬롯 생성
    total_created = 0
    for i in range(0, len(slots_to_create), batch_size):
        batch = slots_to_create[i:i+batch_size]
        batch_created = Slot.objects.bulk_create(batch)
        created_slots.extend(batch_created)
        total_created += len(batch_created)
    
    return total_created, created_slots
