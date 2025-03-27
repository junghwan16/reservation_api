from typing import Dict, Union

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Slot


class SlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Slot
        fields = [
            "id",
            "slot_start_time",
            "slot_end_time",
            "capacity_used",
        ]
