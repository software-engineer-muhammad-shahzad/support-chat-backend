from django.contrib import admin

from .models import Message


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "content", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content", "sender__email", "sender__username")
    autocomplete_fields = ("conversation", "sender")
    readonly_fields = ("created_at", "updated_at")
