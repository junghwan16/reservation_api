from django.urls import path

from .views import AvailableDatesAPIView, AvailableDaySlotsAPIView

urlpatterns = [
    path(
        "available-dates/", AvailableDatesAPIView.as_view(), name="slot-available-dates"
    ),
    path("day-slots/", AvailableDaySlotsAPIView.as_view(), name="slot-day-slots"),
]
