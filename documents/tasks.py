import logging

from celery import shared_task

from .models import Document
from .services.broadcast import broadcast_document_status
from .services.ingestion import run_ingestion

logger = logging.getLogger(__name__)

# Exponential-ish backoff: 15s, 30s, 45s between attempts (Celery's own
# retry_backoff would double each time instead — this is deliberately
# gentler since the usual failure mode here is Gemini's rate limit, which
# doesn't need a long wait, just a moment).
RETRY_DELAY_SECONDS = 15
MAX_RETRIES = 3


@shared_task(bind=True, max_retries=MAX_RETRIES)
def ingest_document_task(self, document_id):
    """Extract/chunk/embed one document in the background, on whichever
    Celery worker picks it up next (broker: CloudAMQP/RabbitMQ — see
    config/celery.py and CELERY_BROKER_URL). Queued right after upload
    (DocumentUploadView) and, for a document that ended up "failed",
    re-queued by DocumentIngestView as a manual retry trigger.

    Running this off the request thread is the actual point of all of
    this: a slow or rate-limited Gemini call used to hold a Django worker
    (and an HTTP connection) open for its whole duration; now it just
    occupies a Celery worker slot, and multiple uploads can be ingested
    concurrently across worker processes instead of queueing behind each
    other on a single request thread.
    """
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        # Deleted (or never existed) before a worker got to it — nothing
        # to process and nothing to retry.
        logger.warning(
            "ingest_document_task: document %s no longer exists", document_id
        )
        return

    document.status = "processing"
    document.save(update_fields=["status", "updated_at"])

    try:
        run_ingestion(document)
    except Exception as exc:
        attempt = self.request.retries + 1
        logger.exception(
            "Ingestion failed for document %s (attempt %s/%s)",
            document_id,
            attempt,
            MAX_RETRIES + 1,
        )
        if self.request.retries >= self.max_retries:
            # Every attempt (the initial try plus MAX_RETRIES retries) has
            # now failed. Checked ourselves rather than catching
            # MaxRetriesExceededError from self.retry() below — that
            # exception is only raised when retry() is called *without*
            # an `exc=` argument; passing exc= (which we want, so Celery
            # records the real failure reason) makes retry() re-raise
            # that exact exception instead once retries run out. Verified
            # directly: with exc= set, the exception that comes back on
            # the final attempt is the original one, never
            # MaxRetriesExceededError — so checking the count first,
            # before ever calling retry() again, is what actually works.
            document.status = "failed"
            document.save(update_fields=["status", "updated_at"])
            broadcast_document_status(document)
            return
        raise self.retry(exc=exc, countdown=RETRY_DELAY_SECONDS * attempt)

    document.status = "completed"
    document.save(update_fields=["status", "updated_at"])
    broadcast_document_status(document)
