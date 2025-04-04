from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ReservationViewSet

router = DefaultRouter()
router.register(r"", ReservationViewSet, basename="reservation")

urlpatterns = [
    path("", include(router.urls)),
]
