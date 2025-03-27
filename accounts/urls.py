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
    # 회원가입
    path("register/", RegisterView.as_view(), name="register"),
    # 로그인 (토큰 발급)
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    # 토큰 갱신
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # 내 정보 조회 및 수정
    path("profile/", UserProfileView.as_view(), name="user_profile"),
    # 비밀번호 변경
    path("change-password/", ChangePasswordView.as_view(), name="change_password"),
    # 로그아
    path("logout/", logout_view, name="logout"),
]
