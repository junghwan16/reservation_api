from django_filters import rest_framework as df_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, viewsets

from .models import Slot
from .serializers import SlotSerializer


class SlotFilter(df_filters.FilterSet):
    date = df_filters.DateFilter(field_name="slot_start_time", lookup_expr="date")
    start = df_filters.DateTimeFilter(field_name="slot_start_time", lookup_expr="gte")
    end = df_filters.DateTimeFilter(field_name="slot_end_time", lookup_expr="lte")
    available = df_filters.BooleanFilter(method='filter_available')

    class Meta:
        model = Slot
        fields = ["date", "start", "end", "available"]
        
    def filter_available(self, queryset, name, value):
        """
        수용 가능한 여유 공간이 있는 슬롯만 필터링합니다.
        available=true 파라미터를 사용하면 꽉 찬 슬롯은 제외됩니다.
        """
        if value:
            return queryset.filter(capacity_used__lt=Slot.MAX_CAPACITY)
        return queryset


@extend_schema_view(
    list=extend_schema(
        summary="슬롯 목록 조회",
        description="사용 가능한 모든 슬롯을 조회합니다. 날짜 또는 시간 범위로 필터링할 수 있습니다.",
        tags=["슬롯"],
        parameters=[
            OpenApiParameter(
                name="date",
                description="특정 날짜의 슬롯만 조회 (YYYY-MM-DD 형식)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="start",
                description="이 시간 이후의 슬롯만 조회 (YYYY-MM-DDThh:mm:ssZ 형식)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="end",
                description="이 시간 이전의 슬롯만 조회 (YYYY-MM-DDThh:mm:ssZ 형식)",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                name="available",
                description="true로 설정 시 여유 공간이 있는 슬롯만 조회",
                required=False,
                type=bool,
            ),
        ],
    ),
    retrieve=extend_schema(
        summary="슬롯 상세 조회", 
        description="특정 슬롯의 상세 정보를 조회합니다.",
        tags=["슬롯"]
    ),
)
class SlotViewSet(viewsets.ReadOnlyModelViewSet):
    """
    슬롯 정보를 제공하는 API 뷰셋입니다.
    GET /api/slots/ - 모든 슬롯을 반환합니다.
    GET /api/slots/?date=2025-04-15 - 특정 날짜의 슬롯을 반환합니다.
    GET /api/slots/?start=2025-04-15T00:00:00Z&end=2025-04-15T23:59:59Z - 특정 기간의 슬롯을 반환합니다.
    GET /api/slots/?available=true - 여유 공간이 있는 슬롯만 반환합니다.
    """

    queryset = Slot.objects.all().order_by("slot_start_time")
    serializer_class = SlotSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = SlotFilter
    ordering_fields = ["slot_start_time", "capacity_used"]
