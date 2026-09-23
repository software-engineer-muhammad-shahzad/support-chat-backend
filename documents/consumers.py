from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .models import Document


class DocumentStatusConsumer(AsyncJsonWebsocketConsumer):
    """One connection per document. Lets the frontend learn the moment
    ingestion (documents/tasks.py::ingest_document_task) settles, instead
    of polling GET /documents/<id>/ on a timer.

    Sends the document's *current* status immediately on connect, before
    anything else. Ingestion is queued the instant the document is created
    (DocumentUploadView) — often finishing in a few seconds — so it can
    easily settle before the client's socket handshake completes; without
    this, a client that connects even slightly late would wait forever for
    a push event that already happened.
    """

    async def connect(self):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        # Accept first, then validate ownership — see ChatConsumer for why
        # (a slow DB round-trip shouldn't hold the handshake open).
        await self.accept()

        document_id = self.scope["url_route"]["kwargs"]["document_id"]
        current_status = await self._get_owned_status(user, document_id)
        if current_status is None:
            await self.close(code=4403)
            return

        self.group_name = f"document_{document_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

        await self.send_json(
            {
                "type": "document_status",
                "document_id": int(document_id),
                "status": current_status,
            }
        )

    async def disconnect(self, close_code):
        group_name = getattr(self, "group_name", None)
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def document_status(self, event):
        """Group-send handler for `{"type": "document.status", ...}` —
        pushed by ingest_document_task (via services/broadcast.py) the
        moment a document's status changes."""
        await self.send_json(
            {
                "type": "document_status",
                "document_id": event["document_id"],
                "status": event["status"],
            }
        )

    @staticmethod
    @database_sync_to_async
    def _get_owned_status(user, document_id):
        return (
            Document.objects.filter(pk=document_id, owner=user)
            .values_list("status", flat=True)
            .first()
        )
