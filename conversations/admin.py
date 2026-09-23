from django.contrib import admin

from .models import Conversation


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "subject", "customer", "agent", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("subject", "customer__email", "customer__username", "agent__email")
    autocomplete_fields = ("customer", "agent")
    readonly_fields = ("created_at", "updated_at")
