from django.conf import settings
from django.db import models


class Conversation(models.Model):

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ASSIGNED = "assigned", "Assigned"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    subject = models.CharField(max_length=255)

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer_conversations",
    )

    agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_conversations",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    # Soft delete, per side. "Removing" a conversation (any status but
    # closed) just hides it from that side's own list — the row, its
    # messages and everyone else's view are untouched. Nothing here is ever
    # hard-deleted, and new activity un-hides it again
    # (chat_messages.views.MessageListCreateView).
    is_customer_deleted = models.BooleanField(default=False)
    is_agent_deleted = models.BooleanField(default=False)
    # Admin-tier isn't tied to one specific user the way customer/agent are
    # — every admin/super_admin shares one "oversight" view — so this hides
    # it from that whole tier at once, not from one particular admin.
    is_admin_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Conversation #{self.id}"
