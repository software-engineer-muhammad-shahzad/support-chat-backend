from rest_framework import serializers

from accounts.models import User
from chat_messages.presence import is_online

from .models import Conversation


class ParticipantSerializer(serializers.ModelSerializer):
    """Lightweight, read-only view of a user embedded in a conversation/message.

    `online` is computed from Redis on every request — never stored in
    Postgres. It reflects whether this user currently has a live
    `ws/chat/...` connection open (see `chat_messages/presence.py`).

    A view serializing many of these at once (a conversation list, a
    message thread) should pass `context={"online_ids": bulk_online_ids(...)}`
    — one batched Redis round-trip instead of one per participant, which on
    a remote Redis (network RTT, not Redis's own speed, is the cost) adds up
    fast: 10 messages in a thread used to mean 10 sequential round-trips.
    Falls back to a live per-object check if a caller doesn't batch.
    """

    online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "role", "online"]
        read_only_fields = fields

    def get_online(self, obj) -> bool:
        online_ids = self.context.get("online_ids")
        if online_ids is not None:
            return obj.id in online_ids
        return is_online(obj.id)


class ConversationSerializer(serializers.ModelSerializer):
    """Read representation."""

    customer = ParticipantSerializer(read_only=True)
    agent = ParticipantSerializer(read_only=True)

    class Meta:
        model = Conversation
        fields = ["id", "subject", "customer", "agent", "status", "created_at", "updated_at"]
        read_only_fields = fields


class ConversationCreateSerializer(serializers.Serializer):
    """Starting a conversation IS sending the first message — one request does both."""

    subject = serializers.CharField(max_length=255, trim_whitespace=True)
    message = serializers.CharField(trim_whitespace=True)

    def validate_subject(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Subject is required.")
        return value

    def validate_message(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Message is required.")
        return value


class ConversationStatusSerializer(serializers.Serializer):
    """Resolve / reopen / close — the only mutation a detail PATCH allows.
    Who's allowed to set which value is enforced in the view, not here (a
    customer may only move resolved -> closed; agent/admin can set any of
    these at any time)."""

    status = serializers.ChoiceField(
        choices=[Conversation.Status.OPEN, Conversation.Status.RESOLVED, Conversation.Status.CLOSED]
    )


class ConversationAssignSerializer(serializers.Serializer):
    """Admin console: assign this conversation to any active agent."""

    agent_id = serializers.PrimaryKeyRelatedField(
        source="agent",
        queryset=User.objects.filter(role=User.Role.AGENT, is_active=True),
    )
