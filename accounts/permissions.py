from rest_framework.permissions import BasePermission

from .models import User


class IsAdminRole(BasePermission):
    """Allow only authenticated users whose app role is 'admin'."""

    message = "You must be an admin to do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
