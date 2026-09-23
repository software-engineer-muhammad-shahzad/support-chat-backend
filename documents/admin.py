from django.contrib import admin
from django.core.files.storage import default_storage
from django.utils.html import format_html

from .models import Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ["name", "status", "file_size", "created_at"]
    readonly_fields = ["file_url"]

    @admin.display(description="URL")
    def file_url(self, obj):
        # Not a stored column — same signed URL the API computes on the fly
        # (see DocumentSerializer.get_url). Recomputed on every admin page
        # load, so it's never stale even though it expires after 1 hour.
        if not obj.file_path:
            return "—"
        url = default_storage.url(obj.file_path)
        return format_html('<a href="{0}" target="_blank">{0}</a>', url)
