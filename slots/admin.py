from django.contrib import admin

from .models import Slot


@admin.register(Slot)
class SlotAdmin(admin.ModelAdmin):
    list_display = [
        "slot_start_time",
        "slot_end_time",
        "capacity_used",
        "remaining_capacity",
        "created_at",
    ]
    list_filter = ["slot_start_time", "capacity_used"]
    search_fields = ["slot_start_time"]
    date_hierarchy = "slot_start_time"
    readonly_fields = ["created_at", "updated_at"]

    def remaining_capacity(self, obj):
        """슬롯의 남은 수용 인원을 표시합니다."""
        return obj.remaining_capacity()

    remaining_capacity.short_description = "남은 수용 인원"
