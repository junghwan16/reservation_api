import json

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class AccountsAPITest(TestCase):
    """계정 관련 API에 대한 테스트"""

    def setUp(self):
        """테스트 클라이언트 설정 및 테스트용 사용자 생성"""
        self.client = APIClient()

        # 테스트용 관리자 생성
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass",
            first_name="관리자",
            last_name="이름",
        )

        # 테스트용 일반 사용자 생성
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
            first_name="테스트",
            last_name="사용자",
        )

        # API URL
        self.register_url = reverse("register")
        self.login_url = reverse("token_obtain_pair")
        self.profile_url = reverse("user_profile")
        self.change_password_url = reverse("change_password")
        self.logout_url = reverse("logout")

    def get_tokens_for_user(self, user):
        """사용자에 대한 JWT 토큰 생성"""
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
        }

    def test_register_user(self):
        """회원가입 테스트"""
        data = {
            "username": "newuser",
            "email": "new@example.com",
            "password": "newpassword123!",
            "first_name": "새로운",
            "last_name": "사용자",
        }

        response = self.client.post(self.register_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="newuser").exists())

        # 생성된 사용자 정보 확인
        user = User.objects.get(username="newuser")
        self.assertEqual(user.email, "new@example.com")
        self.assertEqual(user.first_name, "새로운")
        self.assertEqual(user.last_name, "사용자")
        self.assertTrue(user.check_password("newpassword123!"))

    def test_register_validation(self):
        """회원가입 유효성 검사 테스트"""
        # 필수 필드 누락 테스트
        data = {"username": "newuser", "password": "password123!"}

        response = self.client.post(self.register_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data["details"])
        self.assertIn("first_name", response.data["details"])
        self.assertIn("last_name", response.data["details"])

        # 이미 존재하는 사용자 이름 테스트
        data = {
            "username": "testuser",  # 이미 존재하는 사용자 이름
            "email": "new@example.com",
            "password": "password123!",
            "first_name": "새로운",
            "last_name": "사용자",
        }

        response = self.client.post(self.register_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", response.data["details"])

    def test_login(self):
        """로그인 테스트"""
        data = {"username": "testuser", "password": "testpass"}

        response = self.client.post(self.login_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        # 토큰을 발급 받았는지 확인만 합니다
        # JWT 토큰의 페이로드는 테스트하지 않음

    def test_login_invalid_credentials(self):
        """잘못된 자격 증명으로 로그인 테스트"""
        data = {"username": "testuser", "password": "wrongpass"}

        response = self.client.post(self.login_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile(self):
        """사용자 프로필 조회 테스트"""
        # 토큰 획득
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        response = self.client.get(self.profile_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["username"], "testuser")
        self.assertEqual(response.data["data"]["email"], "test@example.com")
        self.assertEqual(response.data["data"]["first_name"], "테스트")
        self.assertEqual(response.data["data"]["last_name"], "사용자")

    def test_update_profile(self):
        """사용자 프로필 수정 테스트"""
        # 토큰 획득
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        data = {"first_name": "변경된", "last_name": "이름"}

        response = self.client.patch(self.profile_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["first_name"], "변경된")
        self.assertEqual(response.data["data"]["last_name"], "이름")

        # 데이터베이스에서 변경 확인
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "변경된")
        self.assertEqual(self.user.last_name, "이름")

    def test_update_profile_unauthenticated(self):
        """인증되지 않은 사용자의 프로필 수정 시도 테스트"""
        data = {"first_name": "변경된", "last_name": "이름"}

        response = self.client.patch(self.profile_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password(self):
        """비밀번호 변경 테스트"""
        # 토큰 획득
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        data = {"old_password": "testpass", "new_password": "newpassword123!"}

        response = self.client.post(self.change_password_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 비밀번호가 변경되었는지 확인
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("newpassword123!"))

    def test_change_password_incorrect_old_password(self):
        """잘못된 현재 비밀번호로 비밀번호 변경 시도 테스트"""
        # 토큰 획득
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        data = {"old_password": "wrongpass", "new_password": "newpassword123!"}

        response = self.client.post(self.change_password_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("old_password", response.data["details"])

    def test_logout(self):
        """로그아웃 테스트"""
        # 토큰 획득
        tokens = self.get_tokens_for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        data = {"refresh": tokens["refresh"]}

        response = self.client.post(self.logout_url, data=data, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "로그아웃 되었습니다")
