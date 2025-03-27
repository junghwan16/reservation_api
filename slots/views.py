from django_filters import rest_framework as filters
from rest_framework import generics

from .filters import AvailableDatesFilter, AvailableDaySlotsFilter
from .models import Slot
from .serializers import AvailableDateSerializer, SlotSerializer


class AvailableDatesAPIView(generics.ListAPIView):
    """
    한 달 내 예약 가능한 날짜와 각 날짜별 슬롯 수를 반환합니다.
    """

    queryset = Slot.objects.all()
    pagination_class = None
    serializer_class = AvailableDateSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = AvailableDatesFilter


class AvailableDaySlotsAPIView(generics.ListAPIView):
    """
    특정 날짜의 예약 가능한 슬롯 목록을 반환합니다.
    """

    queryset = Slot.objects.all().order_by("slot_start_time")
    pagination_class = None
    serializer_class = SlotSerializer
    filter_backends = [filters.DjangoFilterBackend]
    filterset_class = AvailableDaySlotsFilter
