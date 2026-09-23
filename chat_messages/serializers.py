from rest_framework import serializers

from conversations.serializers import ParticipantSerializer

from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender = ParticipantSerializer(read_only=True)

    class Meta:
        model = Message
        fields = [
            "id",
            "conversation",
            "sender",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "conversation",
            "sender",
            "created_at",
            "updated_at",
        ]
