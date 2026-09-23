from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from conversations.models import Conversation
from conversations.views import scope_conversations_for

from . import presence


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """One connection per conversation. Both participants join the group
    `conversation_<id>`, which carries two kinds of live push:
      - presence (online/offline) — see below,
      - conversation status changes — broadcast by the HTTP views that
        resolve/reopen/close/assign (see conversations.views
        .broadcast_conversation_status); this consumer just forwards them to
        the client via `conversation_status`.

    It also doubles as this user's presence heartbeat — connecting marks
    them online, a `{"type": "ping"}` from the client keeps that alive, and
    disconnecting (or going quiet) marks them offline. See
    `chat_messages/presence.py` for the actual Redis mechanics.

    Presence is also pushed live to the other participant, instead of
    leaving them to find out on their next poll:
      - On connect, everyone else already in this conversation's group is
        told "this user is online" immediately (group_send).
      - The newly-connecting client is, in the same breath, told the
        *other* participant's current status right away — covering the case
        where that other person connected earlier and there's no fresh
        "just came online" event left to broadcast.
      - Going offline is still fundamentally Redis-TTL-driven (a dirty
        disconnect — network drop, laptop closed — has no clean disconnect()
        call to broadcast from), but a clean disconnect still broadcasts
        immediately as a bonus, once we've confirmed via Redis that no other
        connection (another tab) is keeping this user online.
    """

    async def connect(self):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Accept immediately, then validate access. The access check is a DB
        # round-trip (can take a couple seconds on a remote DB) — leaving the
        # socket in the browser's CONNECTING state for that whole window
        # makes it far more likely a React remount (Strict Mode, Fast
        # Refresh, or just navigating away) closes it before it ever opens,
        # which is indistinguishable from a real failure client-side.
        # Accepting first means the browser's `onopen` fires almost
        # instantly; an unauthorized caller still gets disconnected right
        # after, just from the "open" state instead of mid-handshake — no
        # data is ever sent to them either way.
        await self.accept()

        # Mark them online right away — this is a fact about the *user*
        # ("presence:<user_id>" in Redis, not "...in this conversation"), so
        # it doesn't need to wait on the access check below. Doing it first
        # means the connecting user's own status is correct system-wide from
        # the instant their socket opens, rather than only after the DB
        # round-trip that decides whether *this particular* conversation is
        # one they're allowed into.
        self.user = user
        await database_sync_to_async(presence.touch)(user.id, self.channel_name)

        conversation_id = self.scope["url_route"]["kwargs"]["conversation_id"]
        allowed = await self._can_access(user, conversation_id)
        if not allowed:
            await self.close(code=4403)
            return

        self.group_name = f"conversation_{conversation_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.send_json(
            {
                "type": "connection_established",
                "message": "WebSocket connected successfully!",
            }
        )

        # Tell whoever else is already in this conversation's group that
        # this user just came online — instant, no poll wait.
        await self.channel_layer.group_send(
            self.group_name,
            {"type": "presence.message", "user_id": user.id, "online": True},
        )

        # And catch *this* connection up on the other participant's current
        # status right away, in case they connected before we did (so there
        # was no live broadcast for us to have caught).
        other_id = await self._other_participant_id(user, conversation_id)
        if other_id is not None:
            other_online = await database_sync_to_async(presence.is_online)(other_id)
            await self.send_json(
                {"type": "presence", "user_id": other_id, "online": other_online}
            )

    async def disconnect(self, close_code):
        user = getattr(self, "user", None)
        group_name = getattr(self, "group_name", None)
        if user is not None:
            await database_sync_to_async(presence.release)(user.id, self.channel_name)
            if group_name:
                # Only announce "offline" if no other tab/connection for this
                # user is still alive — Redis (not this one socket) is the
                # source of truth for that.
                still_online = await database_sync_to_async(presence.is_online)(user.id)
                if not still_online:
                    await self.channel_layer.group_send(
                        group_name,
                        {
                            "type": "presence.message",
                            "user_id": user.id,
                            "online": False,
                        },
                    )
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        msg_type = content.get("type")

        if msg_type == "ping":
            # Heartbeat — refresh this connection's presence TTL and nothing else.
            await database_sync_to_async(presence.touch)(
                self.user.id, self.channel_name
            )
            await self.send_json({"type": "pong"})
            return

        if msg_type == "typing":
            # Fan the typing state out to the rest of the conversation group.
            # Also counts as activity, so refresh presence while we're here.
            is_typing = bool(content.get("is_typing"))
            await database_sync_to_async(presence.touch)(
                self.user.id, self.channel_name
            )
            group_name = getattr(self, "group_name", None)
            if group_name:
                await self.channel_layer.group_send(
                    group_name,
                    {
                        "type": "typing.message",
                        "user_id": self.user.id,
                        "is_typing": is_typing,
                        "sender_channel": self.channel_name,
                    },
                )
            return

        await self.send_json({"type": "message", "data": content})

    async def presence_message(self, event):
        """Group-send handler for `{"type": "presence.message", ...}` — pushes
        a live online/offline update to this connection's client."""
        await self.send_json(
            {"type": "presence", "user_id": event["user_id"], "online": event["online"]}
        )

    async def conversation_status(self, event):
        """Group-send handler for `{"type": "conversation.status", ...}` —
        pushed by the HTTP view that changed the status. The client treats
        this as a nudge to re-fetch the conversation and confirm against the
        DB, not as the new state itself."""
        await self.send_json(
            {
                "type": "conversation_status",
                "conversation_id": event["conversation_id"],
                "status": event["status"],
            }
        )

    async def typing_message(self, event):
        """Group-send handler for `{"type": "typing.message", ...}` — forwards
        one participant's typing state to the others. Skipped for the sender's
        own connection (you don't need to watch yourself type)."""
        if event.get("sender_channel") == self.channel_name:
            return
        await self.send_json(
            {
                "type": "typing",
                "user_id": event["user_id"],
                "is_typing": event["is_typing"],
            }
        )

    @staticmethod
    @database_sync_to_async
    def _can_access(user, conversation_id) -> bool:
        return scope_conversations_for(
            user, Conversation.objects.filter(pk=conversation_id)
        ).exists()

    @staticmethod
    @database_sync_to_async
    def _other_participant_id(user, conversation_id):
        conversation = (
            Conversation.objects.filter(pk=conversation_id)
            .only("customer_id", "agent_id")
            .first()
        )
        if conversation is None:
            return None
        if conversation.customer_id == user.id:
            return conversation.agent_id
        return conversation.customer_id
