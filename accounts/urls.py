from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ChangePasswordView,
    CustomTokenObtainPairView,
    RegisterView,
    UserProfileView,
    logout_view,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    path("logout/", logout_view, name="logout"),
]
