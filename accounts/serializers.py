from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.validators import EmailValidator
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    사용자 정보 직렬화
    """

    email = serializers.EmailField(validators=[EmailValidator()])

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "is_staff",
            "date_joined",
            "last_login",
        ]
        read_only_fields = ["is_staff", "date_joined", "last_login"]


class RegisterSerializer(serializers.ModelSerializer):
    """
    회원가입 시리얼라이저
    """

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = [
            "username",
            "password",
            "email",
            "first_name",
            "last_name",
        ]
        extra_kwargs = {
            "first_name": {"required": True},
            "last_name": {"required": True},
            "email": {"required": True},
        }

    def validate_username(self, value):
        """사용자 이름 유효성 검증"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("이미 사용 중인 사용자 이름입니다.")
        return value

    def validate_email(self, value):
        """이메일 중복 검증"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("이미 사용 중인 이메일 주소입니다.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    커스텀 토큰 시리얼라이저 - 추가 정보 포함
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # 토큰에 추가 정보 저장
        token["username"] = user.username
        token["email"] = user.email
        token["is_staff"] = user.is_staff
        token["first_name"] = user.first_name
        token["last_name"] = user.last_name
        token["user_id"] = user.id

        return token

    def validate(self, attrs):
        data = super().validate(attrs)

        # 응답에 사용자 기본 정보 추가
        user = self.user
        data.update(
            {
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_staff": user.is_staff,
                "user_id": user.id,
            }
        )

        return data


class ChangePasswordSerializer(serializers.Serializer):
    """
    비밀번호 변경 시리얼라이저
    """

    old_password = serializers.CharField(
        required=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        required=True, validators=[validate_password], style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("현재 비밀번호가 일치하지 않습니다.")
        return value

    def save(self, **kwargs):
        password = self.validated_data["new_password"]
        user = self.context["request"].user
        user.set_password(password)
        user.save()
        return user
