from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from conversations.models import Conversation
from conversations.views import scope_conversations_for
from chat_messages.presence import bulk_online_ids

from .models import Message
from .serializers import MessageSerializer


class MessageListCreateView(generics.ListCreateAPIView):
    """GET/POST messages  one conversation — scoped by the `conversation_id`
    in the URL, and only for someone who can actually see that conversation
    (same rule as the conversation list/detail views: own it as a customer,
    be the assigned agent, or be admin-tier)."""

    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]

    def get_conversation(self):
        conversation = get_object_or_404(
            Conversation, pk=self.kwargs["conversation_id"]
        )
        allowed = scope_conversations_for(
            self.request.user, Conversation.objects.filter(pk=conversation.pk)
        ).exists()
        if not allowed:
            raise PermissionDenied("You do not have access to this conversation.")
        return conversation

    def get_queryset(self):
        conversation = self.get_conversation()
        return (
            Message.objects.filter(conversation=conversation)
            .select_related("sender")
            .order_by("created_at")
        )

    def list(self, request, *args, **kwargs):
        # Same reasoning as ConversationListCreateView.list(): one batched
        # Redis round-trip for every distinct sender in the thread, instead
        # of ParticipantSerializer hitting Redis once per message. A 10+
        # message thread used to mean 10+ sequential round-trips just to
        # know who's online — this is what actually made the thread feel
        # slow to load, presence or not.
        messages = list(self.filter_queryset(self.get_queryset()))
        sender_ids = {m.sender_id for m in messages if m.sender_id}
        context = {
            **self.get_serializer_context(),
            "online_ids": bulk_online_ids(sender_ids),
        }
        serializer = MessageSerializer(messages, many=True, context=context)
        return Response(serializer.data)

    def perform_create(self, serializer):
        conversation = self.get_conversation()
        if conversation.status == Conversation.Status.CLOSED:
            raise PermissionDenied(
                "This conversation is closed. Start a new conversation to keep talking."
            )
        serializer.save(sender=self.request.user, conversation=conversation)

        # A new message un-hides the conversation for whoever had soft-deleted
        # it — a reply must never be silently lost behind someone's "Remove
        # from my list" (customer, agent, or admin-tier's own). The sender
        # can't have deleted it themselves here: get_conversation() wouldn't
        # have let them see it in the first place.
        if (
            conversation.is_customer_deleted
            or conversation.is_agent_deleted
            or conversation.is_admin_deleted
        ):
            conversation.is_customer_deleted = False
            conversation.is_agent_deleted = False
            conversation.is_admin_deleted = False
            conversation.save(
                update_fields=[
                    "is_customer_deleted",
                    "is_agent_deleted",
                    "is_admin_deleted",
                    "updated_at",
                ]
            )
