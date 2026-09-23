import logging

from rest_framework import generics, status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.models import User
from accounts.permissions import ADMIN_TIER_ROLES, IsAdminRole
from chat_messages.models import Message
from chat_messages.presence import bulk_online_ids

from .models import Conversation
from .serializers import (
    ConversationAssignSerializer,
    ConversationCreateSerializer,
    ConversationSerializer,
    ConversationStatusSerializer,
)

logger = logging.getLogger(__name__)


def scope_conversations_for(user, qs):
    """Same access rule everywhere a conversation is looked up:
    - admin-tier: everything, minus what admin-tier itself has removed
      (is_admin_deleted) — a customer's or agent's own soft delete doesn't
      affect this, only admin-tier's.
    - agent: only conversations assigned to them, minus the ones they've
      removed from their queue (is_agent_deleted).
    - customer: only their own, minus the ones they've removed
      (is_customer_deleted).
    """
    if user.role in ADMIN_TIER_ROLES:
        return qs.filter(is_admin_deleted=False)
    if user.role == User.Role.AGENT:
        return qs.filter(agent=user, is_agent_deleted=False)
    return qs.filter(customer=user, is_customer_deleted=False)


def presence_context(conversations) -> dict:
    """One batched Redis round-trip for every customer/agent id across the
    given conversation(s), instead of ParticipantSerializer doing its own
    per-participant call. Pass straight through as a serializer `context`."""
    ids = set()
    for conversation in conversations:
        if conversation.customer_id:
            ids.add(conversation.customer_id)
        if conversation.agent_id:
            ids.add(conversation.agent_id)
    return {"online_ids": bulk_online_ids(ids)}


def broadcast_conversation_status(conversation) -> None:
    """Push the current status to both participants' open WebSockets so their
    UI reacts in real time (composer disables on `closed`, badge updates,
    etc). The client re-fetches from the API on receipt rather than trusting
    the payload blindly — see ChatConsumer.conversation_status.

    Best-effort: a missing or misbehaving channel layer must never break the
    HTTP response that actually changed the status."""
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            f"conversation_{conversation.id}",
            {
                "type": "conversation.status",
                "conversation_id": conversation.id,
                "status": conversation.status,
            },
        )
    except Exception:  # noqa: BLE001 - never let a broadcast failure 500 the request
        logger.warning(
            "broadcast_conversation_status failed for conversation %s",
            conversation.id,
            exc_info=True,
        )


def apply_assignment(conversation, agent) -> None:
    """Assign `agent` to `conversation` and, if it was still sitting
    unclaimed (open), bump it to `assigned` — an open conversation someone
    just picked up isn't "open" anymore. Doesn't touch a conversation that's
    already resolved: reassigning who owns a finished conversation shouldn't
    silently reopen it. A closed conversation can't be (re)assigned at all —
    it's terminal, same as its status (see ConversationDetailView.patch)."""
    if conversation.status == Conversation.Status.CLOSED:
        raise PermissionDenied(
            "This conversation is closed and can no longer be assigned."
        )
    conversation.agent = agent
    fields = ["agent", "updated_at"]
    status_changed = False
    if conversation.status == Conversation.Status.OPEN:
        conversation.status = Conversation.Status.ASSIGNED
        fields.append("status")
        status_changed = True
    conversation.save(update_fields=fields)
    if status_changed:
        broadcast_conversation_status(conversation)


class ConversationListCreateView(generics.ListCreateAPIView):
    """GET  -> conversations scoped to the caller: their own (customer),
              assigned to them (agent), or everything (admin-tier).
    POST -> start one: `{"subject": "...", "message": "..."}`.

    Starting a conversation IS sending the first message — there's no
    "create an empty conversation" step. It's created with status=open.
    """

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Conversation.objects.select_related("customer", "agent")
        return scope_conversations_for(self.request.user, qs).order_by("-updated_at")

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ConversationCreateSerializer
        return ConversationSerializer

    def list(self, request, *args, **kwargs):
        # Bypasses ListModelMixin.list() so the whole page of conversations
        # can share one batched presence lookup instead of one per
        # participant (see `presence_context`) — no pagination is
        # configured, so nothing is lost by fetching it eagerly here.
        conversations = list(self.filter_queryset(self.get_queryset()))
        serializer = ConversationSerializer(
            conversations,
            many=True,
            context={
                **self.get_serializer_context(),
                **presence_context(conversations),
            },
        )
        return Response(serializer.data)

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

        response_serializer = ConversationSerializer(
            conversation, context=presence_context([conversation])
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class ConversationDetailView(generics.RetrieveAPIView):
    """GET    -> one conversation (customer/assigned agent/admin-tier only).
    PATCH  -> change its status: `{"status": "open" | "resolved" | "closed"}`.
              - Agent: any status, any time — resolving/reopening/closing is
                their call to make.
              - Customer: may only close it, and only once it's resolved —
                they can't resolve or reopen it themselves, just confirm
                they're done after the agent has marked it resolved.
              - Admin-tier: never — their role is routing to an agent
                (ConversationAdminAssignView), not touching its status.
              - Closed is terminal: once there, this always 403s, for
                everyone — see the check at the top of `patch()`.
    DELETE -> soft delete: hides this conversation from the caller's own
              side's view only (any status *except* closed — once closed,
              nothing touches it, not even hiding it). Sets
              is_customer_deleted / is_agent_deleted / is_admin_deleted;
              the row, its messages, and everyone else's view are
              untouched. Never a hard delete — and new activity un-hides it
              again (see MessageListCreateView.perform_create).
    """

    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Conversation.objects.select_related("customer", "agent")
        return scope_conversations_for(self.request.user, qs)

    def retrieve(self, request, *args, **kwargs):
        conversation = self.get_object()
        serializer = ConversationSerializer(
            conversation, context=presence_context([conversation])
        )
        return Response(serializer.data)

    def patch(self, request, *args, **kwargs):
        conversation = self.get_object()
        serializer = ConversationStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data["status"]

        # Closed is terminal — nobody (customer, agent, or admin-tier) can
        # change its status again once it's there. Without this, an
        # agent/admin could still cycle a closed conversation back open via
        # closed -> "Resolve" -> resolved -> "Reopen" -> open, quietly
        # undoing the customer's close.
        if conversation.status == Conversation.Status.CLOSED:
            raise PermissionDenied(
                "This conversation is closed and its status can no longer be changed."
            )

        if request.user.role == User.Role.CUSTOMER:
            if new_status != Conversation.Status.CLOSED:
                raise PermissionDenied(
                    "You can only close a conversation, not change its status otherwise — "
                    "resolving or reopening is handled by the agent."
                )
            if conversation.status != Conversation.Status.RESOLVED:
                raise PermissionDenied(
                    "This conversation isn't resolved yet — wait for the agent to resolve it "
                    "before closing."
                )
        elif request.user.role in ADMIN_TIER_ROLES:
            # Admin-tier's only job on a conversation is routing it to an
            # agent (see ConversationAdminAssignView) — the agent owns the
            # whole resolve/reopen/close workflow from there.
            raise PermissionDenied(
                "Admins can't change a conversation's status — assign it to an agent to "
                "have them resolve, reopen, or close it."
            )

        changed = conversation.status != new_status
        conversation.status = new_status
        conversation.save(update_fields=["status", "updated_at"])
        if changed:
            broadcast_conversation_status(conversation)
        return Response(
            ConversationSerializer(
                conversation, context=presence_context([conversation])
            ).data
        )

    def delete(self, request, *args, **kwargs):
        conversation = self.get_object()
        user = request.user

        # Closed is fully terminal now — no option touches it at all, not
        # even removing it from your own list.
        if conversation.status == Conversation.Status.CLOSED:
            raise PermissionDenied(
                "This conversation is closed and can no longer be changed — it can only be viewed."
            )

        if user.role == User.Role.CUSTOMER:
            field = "is_customer_deleted"
        elif user.role == User.Role.AGENT:
            field = "is_agent_deleted"
        else:
            # admin-tier shares one "oversight" view rather than each admin
            # having their own — this hides it from that whole tier at once.
            field = "is_admin_deleted"

        setattr(conversation, field, True)
        conversation.save(update_fields=[field, "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ConversationAdminAssignView(generics.GenericAPIView):
    """POST {"agent_id": <id>} -> assign this conversation to that agent.

    Admin-tier only — the admin console's "assign to any agent" action.
    Distinct from `ConversationSelfAssignView` below (an agent/admin
    assigning themselves, no body needed).

    Assign only, never reassign: admin-tier's whole role here is routing an
    unclaimed conversation to an agent — once it has one, only that agent
    (not the admin) hands it off from there. Trying to pick a different
    agent for an already-assigned conversation 403s.
    """

    queryset = Conversation.objects.all()
    serializer_class = ConversationAssignSerializer
    permission_classes = [IsAdminRole]

    def post(self, request, *args, **kwargs):
        conversation = self.get_object()
        if conversation.agent_id is not None:
            raise PermissionDenied(
                "This conversation is already assigned — admins can assign an "
                "unclaimed conversation, but not reassign one that already has an agent."
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        apply_assignment(conversation, serializer.validated_data["agent"])
        return Response(
            ConversationSerializer(
                conversation, context=presence_context([conversation])
            ).data
        )


class ConversationSelfAssignView(generics.GenericAPIView):
    """POST (no body) -> assign this conversation to the calling agent. The
    "Assign to me" button — agents only. Admin-tier routes conversations to
    agents (ConversationAdminAssignView); they don't pick up work
    themselves, so they can't self-assign here."""

    queryset = Conversation.objects.all()
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user
        if user.role != User.Role.AGENT:
            raise PermissionDenied("Only agents can be assigned a conversation.")
        conversation = self.get_object()
        apply_assignment(conversation, user)
        return Response(
            ConversationSerializer(
                conversation, context=presence_context([conversation])
            ).data
        )
