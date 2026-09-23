import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def broadcast_document_status(document) -> None:
    """Push a document's current status to its open WebSocket, if any
    (documents/consumers.py::DocumentStatusConsumer), so the frontend
    learns the moment ingestion (documents/tasks.py) settles instead of
    waiting on its next poll. Mirrors
    conversations.views.broadcast_conversation_status — same
    group-per-resource pattern, same "nudge only" contract: the client
    re-fetches the document over REST rather than trusting this payload as
    the full truth.

    Best-effort: a missing or misbehaving channel layer must never break
    ingestion itself, which is why this is called from a Celery task
    rather than raising into it.
    """
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(
            f"document_{document.id}",
            {
                "type": "document.status",
                "document_id": document.id,
                "status": document.status,
            },
        )
    except Exception:  # noqa: BLE001 - never let a broadcast failure break ingestion
        logger.warning(
            "broadcast_document_status failed for document %s",
            document.id,
            exc_info=True,
        )
