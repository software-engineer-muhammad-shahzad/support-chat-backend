from django.conf import settings
from django.db import models
from pgvector.django import VectorField


class Document(models.Model):
    """A file a user has uploaded for the RAG assistant to answer
    questions about. Uploading and ingesting (extract/chunk/embed —
    services/ingestion.py) are two separate steps/requests; `status`
    tracks where in that pipeline this row currently is:
      uploaded    -> file is in storage, not chunked/embedded yet
      processing  -> ingest/ is running right now
      completed   -> has embedded chunks, answerable via ask/
      failed      -> ingestion errored (see logs); file still exists
    """

    STATUS_CHOICES = [
        ("uploaded", "Uploaded"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    name = models.CharField(max_length=255)

    # Deliberately a plain CharField, not a Django FileField: the actual
    # bytes live in Supabase Storage (config/settings.py's S3-compatible
    # backend), reached through default_storage directly wherever this app
    # touches a file (views.py, services/ingestion.py) — this column is
    # just the storage key those calls take, e.g. "documents/notes.pdf".
    file_path = models.CharField(max_length=500)

    file_size = models.BigIntegerField(
        null=True,
        blank=True,
    )

    file_type = models.CharField(
        max_length=100,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="uploaded",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class DocumentChunk(models.Model):
    """One splitter-sized piece of a Document's extracted text
    (services/chunking.py), plus its embedding once services/embeddings.py
    has run. Deleting the parent Document cascades here — a chunk never
    outlives the document it came from, and vice versa there's no
    "orphaned embedding" cleanup to worry about."""

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="chunks",
    )

    content = models.TextField()

    # Position within the document, in extraction order — lets
    # generation.py cite "Chunk 3 of notes.pdf" and, if a chunk needs
    # re-embedding later, its neighbors are still identifiable.
    chunk_index = models.PositiveIntegerField()

    # 1536 must match the output_dimensionality passed to
    # generate_embedding() (services/embeddings.py) — pgvector needs a
    # fixed size up front, and retrieval.py's CosineDistance comparison
    # only works when every embedding in the table has the same dimension.
    embedding = VectorField(
        dimensions=1536,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document.name} - Chunk {self.chunk_index}"
