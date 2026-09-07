from django.contrib.auth import get_user_model
from rest_framework import serializers

from .base import StrictFieldsMixin

User = get_user_model()


class UserProfileSerializer(serializers.ModelSerializer):
    """Read representation returned by GET and after a successful update."""

    class Meta:
        model = User
        fields = ["id", "username", "email", "phone", "role", "date_joined"]
        read_only_fields = fields


class UserProfileUpdateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """A user editing their OWN profile — username/phone only.

    Email, role, and password are deliberately not editable here: email +
    role changes go through the admin API, password changes get a dedicated
    endpoint later.
    """

    class Meta:
        model = User
        fields = ["username", "phone"]
        extra_kwargs = {
            "username": {"required": False, "allow_blank": False},
            "phone": {"required": False, "allow_blank": True},
        }
