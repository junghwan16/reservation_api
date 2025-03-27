from django_filters import rest_framework as df_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import filters, viewsets

from .models import Slot
from .serializers import SlotSerializer


class SlotFilter(df_filters.FilterSet):
    """
    슬롯 필터링을 위한 필터셋
    
    여러 조건으로 슬롯을 필터링할 수 있습니다:
    - 특정 날짜
    - 시작 시간 이후
    - 종료 시간 이전
    - 여유 공간 유무
    """
    date = df_filters.DateFilter(
        field_name="slot_start_time",
        lookup_expr="date",
        help_text="특정 날짜의 슬롯 필터링 (YYYY-MM-DD)"
    )
    start = df_filters.DateTimeFilter(
        field_name="slot_start_time",
        lookup_expr="gte",
        help_text="이 시간 이후의 슬롯 필터링"
    )
    end = df_filters.DateTimeFilter(
        field_name="slot_end_time",
        lookup_expr="lte",
        help_text="이 시간 이전의 슬롯 필터링"
    )
    available = df_filters.BooleanFilter(
        method='filter_available',
        help_text="true로 설정 시 여유 공간이 있는 슬롯만 조회"
    )

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
        description="사용 가능한 모든 슬롯을 조회합니다. 날짜, 시간 범위, 여유 공간 여부 등으로 필터링할 수 있습니다.",
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
            OpenApiParameter(
                name="ordering",
                description="정렬 기준 필드 (예: slot_start_time, -slot_start_time, capacity_used)",
                required=False,
                type=str,
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
    
    슬롯은 특정 시간대에 예약할 수 있는 단위로, 각 슬롯은 시작 시간, 종료 시간, 
    그리고 현재까지 예약된 인원수(capacity_used)와 최대 수용 인원(MAX_CAPACITY)을 갖고 있습니다.
    
    사용 가능한 엔드포인트:
    - GET /api/slots/ - 모든 슬롯 목록 조회 (필터링, 정렬 가능)
    - GET /api/slots/{id}/ - 특정 슬롯 상세 조회
    
    필터링 예시:
    - GET /api/slots/?date=2025-04-15 - 특정 날짜의 슬롯을 반환합니다.
    - GET /api/slots/?start=2025-04-15T00:00:00Z&end=2025-04-20T23:59:59Z - 특정 기간의 슬롯을 반환합니다.
    - GET /api/slots/?available=true - 여유 공간이 있는 슬롯만 반환합니다.
    - GET /api/slots/?ordering=slot_start_time - 시작 시간 기준으로 정렬합니다.
    """

    queryset = Slot.objects.all().order_by("slot_start_time")
    serializer_class = SlotSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = SlotFilter
    ordering_fields = ["slot_start_time", "slot_end_time", "capacity_used"]
    ordering = ["slot_start_time"]
