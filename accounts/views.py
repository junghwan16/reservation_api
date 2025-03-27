from django.contrib.auth import get_user_model, logout
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, permissions, serializers, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    회원가입 API

    새로운 사용자 계정을 생성합니다.
    ---
    username, email, password, first_name, last_name을 필수로 입력해야 합니다.
    """

    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "회원가입 실패", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.save()
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "message": "회원가입이 완료되었습니다",
                "data": {
                    "user": UserSerializer(user).data,
                    "tokens": {
                        "refresh": str(refresh),
                        "access": str(refresh.access_token),
                    },
                },
            },
            status=status.HTTP_201_CREATED,
        )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    로그인 API - JWT 토큰 발급

    사용자 이름과 비밀번호를 사용하여 JWT 토큰을 발급합니다.
    ---
    로그인 성공 시 access token과 refresh token을 반환합니다.
    """

    serializer_class = CustomTokenObtainPairSerializer


class UserProfileView(APIView):
    """
    사용자 정보 조회 및 수정 API

    인증된 사용자의 정보를 조회하고 수정할 수 있는 API입니다.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer  # DRF Spectacular를 위한 시리얼라이저 클래스 지정

    def get(self, request):
        """
        현재 로그인한 사용자의 정보를 조회합니다.
        """
        serializer = UserSerializer(request.user)
        return Response(
            {
                "message": "사용자 정보를 성공적으로 조회했습니다",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

    def patch(self, request):
        """
        사용자 정보를 부분적으로 업데이트합니다.

        first_name, last_name, email 등을 수정할 수 있습니다.
        """
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "사용자 정보가 업데이트되었습니다",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": "정보 업데이트 실패", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ChangePasswordView(APIView):
    """
    비밀번호 변경 API

    현재 로그인한 사용자의 비밀번호를 변경합니다.
    """

    # DRF Spectacular를 위한 시리얼라이저 클래스 지정
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        비밀번호 변경을 처리합니다.

        현재 비밀번호, 새 비밀번호가 필요합니다.
        """
        serializer = ChangePasswordSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "비밀번호가 성공적으로 변경되었습니다"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": "비밀번호 변경 실패", "details": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LogoutSerializer(serializers.Serializer):
    """로그아웃 시리얼라이저"""

    refresh = serializers.CharField(required=True)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    로그아웃 API

    현재 로그인된 사용자의 세션을 종료하고 토큰을 블랙리스트에 추가합니다.
    """
    try:
        refresh_token = request.data.get("refresh")
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()  # 토큰을 블랙리스트에 추가

        logout(request)  # Django 기본 로그아웃 함수 호출

        return Response({"message": "로그아웃 되었습니다"}, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {"error": f"로그아웃 중 오류가 발생했습니다: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
