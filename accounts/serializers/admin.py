from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from chat_messages.presence import is_online

from .base import StrictFieldsMixin

User = get_user_model()

# super_admin can never be granted through the API — only via
# `manage.py create_superadmin`. Every role-accepting serializer below is
# restricted to this list as defense in depth, on top of the view-level checks.
ASSIGNABLE_ROLES = [
    choice for choice in User.Role.choices if choice[0] != User.Role.SUPER_ADMIN
]


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


class AgentWorkloadSerializer(serializers.ModelSerializer):
    """One agent's current load, for the admin "who should I assign this
    to?" decision — see AgentWorkloadView. `workload` comes from an
    `annotate(Count(...))` on the queryset, not a DB column, so it's
    read-only and only ever populated by that view."""

    workload = serializers.IntegerField(read_only=True)
    online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "workload", "online"]
        read_only_fields = fields

    def get_online(self, obj) -> bool:
        online_ids = self.context.get("online_ids")
        if online_ids is not None:
            return obj.id in online_ids
        return is_online(obj.id)


class AdminUserCreateSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    """An admin creates a user with an explicit role (customer / agent / admin)."""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True, default=""
    )
    role = serializers.ChoiceField(choices=ASSIGNABLE_ROLES)

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
    """Promote / demote a user's profile fields and role.

    Active/inactive is deliberately not here — that's
    AdminUserActivateView / AdminUserDeactivateView's job.
    """

    role = serializers.ChoiceField(choices=ASSIGNABLE_ROLES, required=False)

    class Meta:
        model = User
        fields = ["username", "phone", "role"]

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if "role" in validated_data:
            instance.is_staff = instance.role == User.Role.ADMIN
            instance.save(update_fields=["is_staff"])
        return instance
