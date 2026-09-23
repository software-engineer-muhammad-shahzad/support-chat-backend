from django.core.files.storage import default_storage
from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    # Not stored on the model — resolved from file_path through the default
    # storage backend (Supabase Storage, see config/settings.py) so the
    # frontend has something to link/preview without knowing how storage
    # URLs are built.
    url = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "name",
            "file_path",
            "file_size",
            "file_type",
            "status",
            "url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_url(self, obj):
        if not obj.file_path:
            return None
        return default_storage.url(obj.file_path)
