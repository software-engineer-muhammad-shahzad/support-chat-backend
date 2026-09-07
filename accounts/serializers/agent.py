"""Admin-only agent management serializers — same `User` model, `role="agent"`."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import User

from .base import StrictFieldsMixin


class AgentSerializer(serializers.ModelSerializer):
    """Read representation used for list / detail."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "role", "is_active", "date_joined"]
        read_only_fields = fields


class AgentCreateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """An admin creates a support agent. Role is always 'agent' — not a client input."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "password"]
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
        return User.objects.create_user(role=User.Role.AGENT, is_staff=False, **validated_data)


class AgentUpdateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """Edit an agent's profile fields.

    Role stays 'agent' here — use /api/admin/users/<id>/ to change a user's
    role. Active/inactive is deliberately not here either — that's
    AdminUserActivateView / AdminUserDeactivateView's job.
    """

    class Meta:
        model = User
        fields = ["username", "phone"]
