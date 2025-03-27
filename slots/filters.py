from django.db.models import Count
from django.db.models.functions import TruncDate
from django_filters import rest_framework as filters
from rest_framework.exceptions import ValidationError

from .models import Slot
from .utils import get_month_range


class AvailableDatesFilter(filters.FilterSet):
    year = filters.NumberFilter(required=True)
    month = filters.NumberFilter(required=True)

    class Meta:
        model = Slot
        fields = []

    def filter_queryset(self, queryset):
        data = self.data

        try:
            year = int(data.get("year"))
            month = int(data.get("month"))
        except (TypeError, ValueError):
            raise ValidationError("year와 month는 정수여야 합니다.")

        if not (1 <= month <= 12):
            raise ValidationError("month는 1부터 12 사이여야 합니다.")

        start_date, end_date = get_month_range(year, month)

        return (
            queryset.filter(
                slot_start_time__range=(start_date, end_date),
                capacity_used__lt=Slot.MAX_CAPACITY,
            )
            .annotate(date=TruncDate("slot_start_time"))
            .values("date")
            .annotate(available_slots_count=Count("id"))
            .order_by("date")
        )


class AvailableDaySlotsFilter(filters.FilterSet):
    # slot_start_time의 날짜 부분으로 필터링: YYYY-MM-DD 형식
    date = filters.DateFilter(
        field_name="slot_start_time", lookup_expr="date", required=True
    )
    # available 파라미터가 true이면 capacity_used 조건을 추가
    available = filters.BooleanFilter(method="filter_available", required=False)

    class Meta:
        model = Slot
        fields = []  # model의 직접 필드와 연결하지 않음

    def filter_available(self, queryset, name, value):
        if value:
            return queryset.filter(capacity_used__lt=Slot.MAX_CAPACITY)
        return queryset
