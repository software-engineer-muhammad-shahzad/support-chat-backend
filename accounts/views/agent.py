"""Admin-only agent management API (/api/admin/agents/)."""

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import IsAdminRole
from accounts.serializers import AgentCreateSerializer, AgentSerializer, AgentUpdateSerializer


class AdminAgentListCreateView(generics.ListCreateAPIView):
    """GET  -> list every support agent.  POST -> create one."""

    queryset = User.objects.filter(role=User.Role.AGENT).order_by("-date_joined")
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return AgentCreateSerializer
        return AgentSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        agent = serializer.save()
        return Response(AgentSerializer(agent).data, status=status.HTTP_201_CREATED)


class AdminAgentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET / PATCH (username, phone, is_active) / DELETE a single agent."""

    queryset = User.objects.filter(role=User.Role.AGENT)
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return AgentUpdateSerializer
        return AgentSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AgentSerializer(self.get_object()).data)

    def perform_destroy(self, instance):
        if instance == self.request.user:
            raise ValidationError("You cannot delete your own account.")
        instance.delete()
