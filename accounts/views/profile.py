"""User profile API  (/api/users/<id>/)."""

from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsSelfOrAdmin
from accounts.serializers import UserProfileSerializer, UserProfileUpdateSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET -> view a profile. PATCH -> update it. Own profile only (or admin)."""

    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, IsSelfOrAdmin]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserProfileUpdateSerializer
        return UserProfileSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()  # runs IsSelfOrAdmin.has_object_permission
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserProfileSerializer(instance).data)
