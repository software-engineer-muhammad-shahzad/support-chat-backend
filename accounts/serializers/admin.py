from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .base import StrictFieldsMixin

User = get_user_model()


class AdminUserSerializer(serializers.ModelSerializer):
    """Read representation used for list / detail."""

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone",
            "role",
            "is_active",
            "is_staff",
            "date_joined",
        ]
        read_only_fields = fields


class AdminUserCreateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """An admin creates a user with an explicit role (customer / agent / admin)."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    role = serializers.ChoiceField(choices=User.Role.choices)

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "password", "role"]
        read_only_fields = ["id"]
        extra_kwargs = {
            "username": {"required": True, "allow_blank": False},
            "email": {"required": True, "allow_blank": False},
        }

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def create(self, validated_data):
        # An 'admin' role also gets Django-admin access; agents/customers don't.
        is_admin = validated_data["role"] == User.Role.ADMIN
        return User.objects.create_user(is_staff=is_admin, **validated_data)


class AdminUserUpdateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """Promote / demote / deactivate a user."""

    role = serializers.ChoiceField(choices=User.Role.choices, required=False)

    class Meta:
        model = User
        fields = ["username", "phone", "role", "is_active"]

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if "role" in validated_data:
            instance.is_staff = instance.role == User.Role.ADMIN
            instance.save(update_fields=["is_staff"])
        return instance
