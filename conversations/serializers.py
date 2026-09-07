from rest_framework import serializers

from .models import Conversation


class ConversationSerializer(serializers.ModelSerializer):
    """Read representation."""

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
