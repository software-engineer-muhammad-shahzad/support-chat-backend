from rest_framework.permissions import BasePermission

from .models import User

# "Admin-tier" = anyone with an admin-level console: admin or super_admin.
ADMIN_TIER_ROLES = (User.Role.ADMIN, User.Role.SUPER_ADMIN)


class IsAdminRole(BasePermission):
    """Allow authenticated users whose app role is 'admin' or 'super_admin'."""

    message = "You must be an admin to do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in ADMIN_TIER_ROLES)


class IsSuperAdminRole(BasePermission):
    """Allow only the super admin — system-level access (managing other admins, etc.)."""

    message = "You must be a super admin to do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.SUPER_ADMIN)


class IsSelfOrAdmin(BasePermission):
    """A user may view/edit their own profile; an admin may view/edit any."""

    message = "You can only view or edit your own profile."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return obj.id == user.id or user.role in ADMIN_TIER_ROLES
