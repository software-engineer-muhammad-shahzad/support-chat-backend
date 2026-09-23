from django.core.files.storage import default_storage
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .services.deletion import delete_documents
from .tasks import ingest_document_task

from .models import Document
from .serializers import DocumentSerializer

# A UI safety net, not a security boundary — Supabase Storage enforces its
# own bucket-level limits regardless of what this rejects up front.
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB


class DocumentUploadView(generics.CreateAPIView):
    """POST a multipart `file` — pushes the bytes straight to Supabase
    Storage through the default file storage backend (config/settings.py),
    records the resulting storage path on a Document row, and queues
    ingestion (extract/chunk/embed — documents/tasks.py) on a Celery
    worker before returning.

    The response comes back as soon as the task is queued — it does NOT
    wait for ingestion to finish. That's the actual point of using Celery
    here: a slow or rate-limited Gemini call no longer ties up this
    request/worker thread, and multiple uploads get ingested concurrently
    across worker processes instead of one at a time behind each other.
    The frontend polls DocumentDetailView (GET /documents/<id>/) to learn
    when `status` moves past "processing".
    """

    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if upload is None:
            raise ValidationError({"file": "No file was submitted."})
        if upload.size > MAX_UPLOAD_SIZE:
            raise ValidationError(
                {
                    "file": f"File is too large (max {MAX_UPLOAD_SIZE // (1024 * 1024)} MB)."
                }
            )

        # upload_to-style prefix, done by hand since file_path is a plain
        # CharField rather than a FileField — default_storage.save() picks
        # a non-colliding name (e.g. "-a1b2c3" suffix) if one already exists
        # at that path, so two people uploading "notes.pdf" don't clobber
        # each other.
        stored_path = default_storage.save(f"documents/{upload.name}", upload)

        document = Document.objects.create(
            owner=request.user,
            name=upload.name,
            file_path=stored_path,
            file_size=upload.size,
            file_type=upload.content_type or "",
            status="processing",
        )
        ingest_document_task.delay(document.id)
        serializer = self.get_serializer(document)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DocumentIngestView(APIView):
    """POST — (re-)queues ingestion for one of the caller's own documents
    on a Celery worker (documents/tasks.py::ingest_document_task) and
    returns immediately with its current status. Upload already triggers
    this automatically; the main reason to call it directly is to manually
    retry a document that ended up "failed" without re-uploading the file.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        document = get_object_or_404(Document, pk=pk, owner=request.user)
        document.status = "processing"
        document.save(update_fields=["status", "updated_at"])
        ingest_document_task.delay(document.id)
        serializer = DocumentSerializer(document)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class DocumentDetailView(generics.RetrieveDestroyAPIView):
    """GET — the caller's own document, most importantly its `status`;
    this is what the frontend polls after upload/ to learn when a
    background ingestion task (documents/tasks.py) has moved past
    "processing" into "completed" or "failed".

    DELETE — completely, not a soft delete: removes the file from
    Supabase Storage, the Document row, and (via DocumentChunk.document's
    on_delete=CASCADE) every one of its chunks along with their pgvector
    embeddings. Nothing is left behind in either the database or storage.
    """

    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user)

    def perform_destroy(self, instance):
        if instance.file_path:
            # Storage and the DB row can't be dropped in one atomic step —
            # delete the file first. If this fails, the DB row (and its
            # chunks/embeddings) are deliberately left in place rather than
            # deleted, so a failed delete never strands an orphaned file in
            # the bucket with nothing pointing back to it.
            default_storage.delete(instance.file_path)
        instance.delete()


class DocumentDeleteAllView(APIView):
    """DELETE — permanently deletes every one of the caller's own
    documents: each storage file, every Document row, and (cascade) every
    chunk and pgvector embedding that came from them. Owner-scoped like
    everything else here — never touches anyone else's documents, "all"
    only ever means "all of mine"."""

    permission_classes = [IsAuthenticated]

    def delete(self, request):
        deleted = delete_documents(Document.objects.filter(owner=request.user))
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


class DocumentBulkDeleteView(APIView):
    """POST {document_ids: [...]} — permanently deletes exactly those of
    the caller's own documents (same guarantees as DocumentDeleteAllView,
    just for a chosen subset rather than everything). This is what backs
    the sidebar's "delete the ones I've checked" action — the multi-select
    checkboxes otherwise only controlled what ask/ searches, with no way to
    act on that same selection.

    POST rather than DELETE-with-a-body: some proxies/clients strip bodies
    on DELETE, and this is more of an action than a canonical resource
    delete anyway. Ids that don't exist or aren't owned by the caller are
    silently excluded rather than erroring the whole batch — the frontend
    only ever offers ids from the caller's own list, so that path is just
    defense against an id going stale mid-request (e.g. deleted twice).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        document_ids = request.data.get("document_ids") or []
        deleted = delete_documents(
            Document.objects.filter(id__in=document_ids, owner=request.user)
        )
        return Response({"deleted": deleted}, status=status.HTTP_200_OK)


class DocumentListView(generics.ListAPIView):
    """GET the caller's own uploaded documents — populates the assistant's
    document picker (all documents / one specific document) in the
    frontend sidebar."""

    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Document.objects.filter(owner=self.request.user).order_by("-created_at")
