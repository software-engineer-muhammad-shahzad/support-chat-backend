from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from chat_messages.models import Message

from .models import Conversation
from .serializers import ConversationCreateSerializer, ConversationSerializer


class ConversationListCreateView(generics.ListCreateAPIView):
    """GET  -> the caller's own conversations.
    POST -> start one: `{"subject": "...", "message": "..."}`.

    Starting a conversation IS sending the first message — there's no
    "create an empty conversation" step. It's created with status=open.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Conversation.objects.filter(customer=self.request.user).order_by("-updated_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ConversationCreateSerializer
        return ConversationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            conversation = Conversation.objects.create(
                customer=request.user,
                subject=serializer.validated_data["subject"],
                status=Conversation.Status.OPEN,
            )
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=serializer.validated_data["message"],
            )

        return Response(ConversationSerializer(conversation).data, status=status.HTTP_201_CREATED)
