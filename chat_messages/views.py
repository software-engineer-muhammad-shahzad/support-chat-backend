from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from .models import Message
from .serializers import MessageSerializer


class MessageListCreateView(generics.ListCreateAPIView):    
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(
            conversation__customer=self.request.user
        ).order_by("created_at")

    def perform_create(self, serializer):
        serializer.save(sender=self.request.user)
