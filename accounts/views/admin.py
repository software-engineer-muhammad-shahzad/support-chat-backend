"""Admin-only user management API  (/api/admin/users/)."""

from django.db.models import Q
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from accounts.pagination import AdminUserPagination
from accounts.permissions import ADMIN_TIER_ROLES, IsAdminRole
from accounts.serializers import (
    AdminUserCreateSerializer,
    AdminUserSerializer,
    AdminUserUpdateSerializer,
)


def _is_super_admin(user) -> bool:
    return user.role == User.Role.SUPER_ADMIN


def _guard_admin_tier_role(requester, role: str) -> None:
    """A plain admin may never touch an admin-or-super-admin-role account."""
    if role in ADMIN_TIER_ROLES and not _is_super_admin(requester):
        raise PermissionDenied("Only a super admin can manage admin accounts.")
    if role == User.Role.SUPER_ADMIN:
        raise PermissionDenied("Super admin accounts can only be created via the CLI.")


def _guard_admin_tier_target(requester, target: User) -> None:
    """A plain admin may never touch an admin-or-super-admin-role account."""
    if target.role in ADMIN_TIER_ROLES and not _is_super_admin(requester):
        raise PermissionDenied("Only a super admin can manage admin accounts.")


class AdminUserListCreateView(generics.ListCreateAPIView):
    """GET  -> list users, optionally `?role=customer|agent|admin&search=`, paginated.
    POST -> create one with a chosen role.

    One endpoint for every admin tab — the frontend just changes `role`,
    `search`, and `page`, instead of fetching everyone and filtering/searching
    client-side.

    Authority: a plain admin can manage customers, agents, and conversations,
    but never other admin-tier accounts (view, create, update, or delete) —
    that's the super admin's job. Super admin accounts themselves are never
    creatable here at all; see `manage.py create_superadmin`.
    """

    queryset = User.objects.order_by("-date_joined")
    permission_classes = [IsAdminRole]
    pagination_class = AdminUserPagination

    def get_queryset(self):
        queryset = super().get_queryset()

        role = self.request.query_params.get("role")
        if role:
            valid_roles = {choice for choice, _ in User.Role.choices}
            if role not in valid_roles:
                raise ValidationError({"role": f"'{role}' is not a valid role."})
            if role in ADMIN_TIER_ROLES and not _is_super_admin(self.request.user):
                raise PermissionDenied("Only a super admin can manage admin accounts.")
            queryset = queryset.filter(role=role)
        elif not _is_super_admin(self.request.user):
            # An unfiltered listing from a plain admin never surfaces other admins.
            queryset = queryset.exclude(role__in=ADMIN_TIER_ROLES)

        search = self.request.query_params.get("search", "").strip()
        if search:
            queryset = queryset.filter(
                Q(username__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )

        return queryset

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AdminUserCreateSerializer
        return AdminUserSerializer

    def create(self, request, *args, **kwargs):
        _guard_admin_tier_role(request.user, request.data.get("role"))
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(AdminUserSerializer(user).data, status=status.HTTP_201_CREATED)


class AdminUserDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH (role, is_active, …) / DELETE a single user."""

    queryset = User.objects.all()
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return AdminUserUpdateSerializer
        return AdminUserSerializer

    def get_object(self):
        obj = super().get_object()
        _guard_admin_tier_target(self.request.user, obj)
        return obj

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            if request.data.get("role") not in (None, instance.role):
                raise ValidationError("You cannot change your own role.")
            if request.data.get("is_active") is False:
                raise ValidationError("You cannot deactivate your own account.")
        new_role = request.data.get("role")
        if new_role is not None:
            _guard_admin_tier_role(request.user, new_role)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(self.get_object()).data)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError("You cannot delete your own account.")
        instance.delete()


class AdminUserDeactivateView(APIView):
    """POST -> deactivate any user — customer, agent, or (super-admin-only)
    another admin. One endpoint for every tab, same authority rules as the
    detail view above.
    """

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        _guard_admin_tier_target(request.user, user)
        if user == request.user:
            raise ValidationError("You cannot deactivate your own account.")
        if user.is_active:
            user.is_active = False
            user.save(update_fields=["is_active"])
        return Response(AdminUserSerializer(user).data)


class AdminUserActivateView(APIView):
    """POST -> reactivate any user."""

    permission_classes = [IsAdminRole]

    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        _guard_admin_tier_target(request.user, user)
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
        return Response(AdminUserSerializer(user).data)
